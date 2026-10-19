"""Evaluate hybrid search ranking and the trip-planning agent's tool use.

    python -m evals.run                     # offline: fake embedder + rule-based planner
    python -m evals.run --provider real     # the configured LLM_* / EMBEDDING_* models
    python -m evals.run --only search --case kacchi --case bangla-biryani

It uses its own database (`<DATABASE_URL name>_eval`), which it creates,
migrates, fills with the dev seed and embeds with the chosen embedder, so the
dev database is never touched. Expected results name seeded places
(search_cases.json, agent_cases.json); a case naming a place the seed doesn't
have stops the run.

Search: each query runs keyword-only and hybrid, scored by hit@3, hit@5 and
MRR over the top 10. Agent: each prompt runs through the real agent loop,
tools and database; scored by tool-call precision and recall, argument
accuracy and the grounding check. Both report p50/p95 latency.

Results go to evals/results/<time>-<provider>.{json,md}; the markdown is also
printed. With a slow local model, raise --embed-timeout and
ASSISTANT_TIMEOUT_S, or slow calls are scored as fallbacks and timeouts.
"""

import argparse
import asyncio
import contextlib
import io
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).parent
SEARCH_LIMIT = 10


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--provider", choices=["fake", "real"], default="fake")
    p.add_argument("--only", choices=["search", "agent"])
    p.add_argument(
        "--case", action="append", default=[], help="run only this case id (repeatable)"
    )
    p.add_argument("--database-url", help="default: <DATABASE_URL name>_eval")
    p.add_argument(
        "--skip-seed", action="store_true", help="the eval database is already seeded"
    )
    p.add_argument(
        "--embed-timeout",
        type=float,
        help="seconds to wait for a query embedding before falling back to keyword "
        "search (default: the app's)",
    )
    p.add_argument("--out", type=Path, default=HERE / "results")
    return p.parse_args(argv)


def eval_database_url(base: str) -> str:
    prefix, name = base.rsplit("/", 1)
    return f"{prefix}/{name.split('?')[0]}_eval"


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def prepare_database(url: str) -> None:
    """Create the eval database if needed and migrate it (before the app's
    engine exists, which binds to the event loop that first uses it)."""
    import asyncpg

    dsn = url.replace("+asyncpg", "")
    server, name = dsn.rsplit("/", 1)

    async def ensure() -> None:
        conn = await asyncpg.connect(server + "/postgres")
        try:
            if not await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1", name
            ):
                await conn.execute(f'CREATE DATABASE "{name}"')
        finally:
            await conn.close()

    asyncio.run(ensure())
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        cwd=HERE.parent,
        env=os.environ.copy(),
        capture_output=True,
    )


def load_cases(name: str, only_ids: list[str]) -> list[dict]:
    cases = json.loads((HERE / name).read_text())
    return [c for c in cases if not only_ids or c["id"] in only_ids]


# ------------------------------------------------------------------- search


async def eval_search(cases: list[dict]) -> dict:
    from app.ai import get_embedder
    from app.core.config import settings
    from app.db.session import AsyncSessionLocal
    from app.services.hybrid_search_service import hybrid_search
    from evals.metrics import (
        first_relevant_rank,
        hit_at,
        mean,
        percentile,
        reciprocal_rank,
    )

    # Load the embedding model first so a cold start isn't timed as query latency.
    with contextlib.suppress(Exception):
        await get_embedder().embed(["warm up"], kind="query", purpose="eval")

    out = {}
    for mode in ("keyword", "hybrid"):
        settings.AI_ENABLED = mode == "hybrid"
        rows = []
        for case in cases:
            start = time.perf_counter()
            async with AsyncSessionLocal() as db:
                found = await hybrid_search(
                    db, case["query"], limit=SEARCH_LIMIT, **case.get("filters", {})
                )
            latency = (time.perf_counter() - start) * 1000
            ranked = [item.name for item in found.items]
            rank = first_relevant_rank(ranked, set(case["expected"]))
            rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "expected": case["expected"],
                    "rank": rank,
                    "top": ranked[:5],
                    "mode": found.mode,
                    "latency_ms": round(latency, 1),
                }
            )
            log(f"  search/{mode} {case['id']}: rank {rank}")
        latencies = [r["latency_ms"] for r in rows]
        out[mode] = {
            "metrics": {
                "hit@3": mean([hit_at(r["rank"], 3) for r in rows]),
                "hit@5": mean([hit_at(r["rank"], 5) for r in rows]),
                "mrr": mean([reciprocal_rank(r["rank"]) for r in rows]),
                "p50_ms": percentile(latencies, 50),
                "p95_ms": percentile(latencies, 95),
                # Hybrid queries answered by keyword search alone because the
                # embedder failed or timed out.
                "fallbacks": sum(r["mode"] != mode for r in rows),
            },
            "cases": rows,
        }
    settings.AI_ENABLED = True
    return out


# -------------------------------------------------------------------- agent


async def eval_agent(cases: list[dict], place_names: dict[str, str]) -> dict:
    from app.ai.agent import run_agent
    from evals.metrics import mean, percentile, precision_recall, score_tool_use

    rows = []
    for case in cases:
        calls, answer, errors, failed_tools = [], [], [], 0
        done: dict = {}
        location = tuple(case["location"]) if case.get("location") else None
        start = time.perf_counter()
        async for event in run_agent(
            [{"role": "user", "content": case["prompt"]}], user_location=location
        ):
            if event.type == "tool_call":
                calls.append(
                    {"name": event.data["name"], "args": event.data["arguments"]}
                )
            elif event.type == "tool_result" and not event.data["ok"]:
                failed_tools += 1
            elif event.type == "token":
                answer.append(event.data["text"])
            elif event.type == "error":
                errors.append(event.data["code"])
            elif event.type == "done":
                done = event.data
        latency = (time.perf_counter() - start) * 1000
        score = score_tool_use(
            calls,
            case["expected_tools"],
            set(case.get("allowed_tools", [])),
            place_names,
        )
        grounding = done.get("grounding") or {}
        rows.append(
            {
                "id": case["id"],
                "prompt": case["prompt"],
                **score,
                "calls": calls,
                "failed_tool_calls": failed_tools,
                "answer": "".join(answer).strip(),
                "finish_reason": done.get("finish_reason"),
                "errors": errors,
                "grounded": not (
                    grounding.get("unverified_places")
                    or grounding.get("unsupported_fares")
                ),
                "grounding": grounding,
                "latency_ms": round(latency, 1),
            }
        )
        log(f"  agent {case['id']}: {[c['name'] for c in calls]} {errors or ''}")

    precision, recall = precision_recall(rows)
    args_total = sum(r["args_total"] for r in rows)
    answered = [r for r in rows if r["answer"]]
    latencies = [r["latency_ms"] for r in rows]
    return {
        "metrics": {
            "tool_precision": precision,
            "tool_recall": recall,
            "arg_accuracy": sum(r["args_ok"] for r in rows) / args_total
            if args_total
            else None,
            # Every expected tool called with every expected argument, nothing
            # unexpected, and the run didn't fail.
            "all_correct": mean(
                [
                    float(
                        not r["fn"]
                        and not r["fp"]
                        and r["args_ok"] == r["args_total"]
                        and not r["errors"]
                    )
                    for r in rows
                ]
            ),
            "grounded_answers": mean([float(r["grounded"]) for r in answered]),
            "failed_tool_calls": sum(r["failed_tool_calls"] for r in rows),
            "errors": sum(bool(r["errors"]) for r in rows),
            "mean_tool_calls": mean([len(r["calls"]) for r in rows]),
            "p50_ms": percentile(latencies, 50),
            "p95_ms": percentile(latencies, 95),
        },
        "cases": rows,
    }


# ------------------------------------------------------------------- report


def _f(value, digits: int = 2) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _ms(value) -> str:
    if value is None:
        return "—"
    return f"{value / 1000:.1f} s" if value >= 1000 else f"{value:.0f} ms"


def markdown(report: dict) -> str:
    meta = report["meta"]
    lines = [
        f"# AI eval: {meta['provider']} ({meta['llm_model']}, {meta['embedding_model']})",
        "",
        f"{meta['started_at']} · database `{meta['database']}`",
    ]
    if search := report.get("search"):
        n = len(search["hybrid"]["cases"])
        lines += [
            "",
            f"## Search ({n} queries, top {SEARCH_LIMIT})",
            "",
            "| Mode | hit@3 | hit@5 | MRR | p50 | p95 |",
            "|---|---|---|---|---|---|",
        ]
        for mode in ("keyword", "hybrid"):
            m = search[mode]["metrics"]
            lines.append(
                f"| {mode} | {_f(m['hit@3'])} | {_f(m['hit@5'])} | {_f(m['mrr'])} "
                f"| {_ms(m['p50_ms'])} | {_ms(m['p95_ms'])} |"
            )
        if fallbacks := search["hybrid"]["metrics"]["fallbacks"]:
            lines += [
                "",
                f"Hybrid fell back to keyword search on {fallbacks} of {n} queries "
                "(embedding failed or timed out).",
            ]
        lines += [
            "",
            "| Query | Expected | Keyword rank | Hybrid rank | Hybrid top 3 |",
            "|---|---|---|---|---|",
        ]
        for kw, hy in zip(
            search["keyword"]["cases"], search["hybrid"]["cases"], strict=True
        ):
            lines.append(
                f"| {hy['query']} | {', '.join(hy['expected'])} | {kw['rank'] or '—'} "
                f"| {hy['rank'] or '—'} | {', '.join(hy['top'][:3])} |"
            )
    if agent := report.get("agent"):
        m = agent["metrics"]
        lines += [
            "",
            f"## Agent ({len(agent['cases'])} prompts)",
            "",
            "| Tool precision | Tool recall | Argument accuracy | All correct "
            "| Grounded answers | Failed tool calls | Errors | p50 | p95 |",
            "|---|---|---|---|---|---|---|---|---|",
            f"| {_f(m['tool_precision'])} | {_f(m['tool_recall'])} "
            f"| {_f(m['arg_accuracy'])} | {_f(m['all_correct'])} "
            f"| {_f(m['grounded_answers'])} | {m['failed_tool_calls']} | {m['errors']} "
            f"| {_ms(m['p50_ms'])} | {_ms(m['p95_ms'])} |",
        ]
        misses = [
            r
            for r in agent["cases"]
            if r["missing"] or r["unexpected"] or r["wrong_args"] or r["errors"]
        ]
        if misses:
            lines += ["", "### Misses", ""]
        for r in misses:
            problems = []
            if r["missing"]:
                problems.append(f"didn't call {', '.join(r['missing'])}")
            if r["unexpected"]:
                problems.append(f"shouldn't call {', '.join(r['unexpected'])}")
            problems += r["wrong_args"]
            if r["errors"]:
                problems.append(f"errors: {', '.join(r['errors'])}")
            lines.append(f"- **{r['id']}**: " + "; ".join(problems))
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- main


async def run(args: argparse.Namespace, database: str) -> dict:
    from sqlalchemy import select

    from app import ai
    from app.ai.fake import FakeEmbedder, FakeLLM
    from app.ai.indexing import embed_all
    from app.db.session import AsyncSessionLocal, engine
    from app.models.place import Place
    from app.services import hybrid_search_service
    from evals import baseline

    if args.provider == "fake":
        ai.set_providers(
            llm=FakeLLM(responder=baseline.respond), embedder=FakeEmbedder()
        )
    if args.embed_timeout:
        hybrid_search_service.QUERY_EMBED_TIMEOUT_S = args.embed_timeout

    try:
        if not args.skip_seed:
            log("Seeding the eval database ...")
            with contextlib.redirect_stdout(io.StringIO()):
                from app.scripts.seed_dev import seed

                await seed()
        log(f"Embedding with {ai.get_embedder().model} ...")
        async with AsyncSessionLocal() as db:
            await embed_all(db)
            place_names = {
                str(pid): name
                for pid, name in await db.execute(
                    select(Place.id, Place.name).where(Place.is_verified.is_(True))
                )
            }

        search_cases = load_cases("search_cases.json", args.case)
        agent_cases = load_cases("agent_cases.json", args.case)
        known = set(place_names.values())
        unknown = {
            name for c in search_cases for name in c["expected"] if name not in known
        }
        if unknown:
            raise SystemExit(f"Cases name places the seed doesn't have: {unknown}")

        report: dict = {
            "meta": {
                "provider": args.provider,
                "llm_model": ai.get_llm().model,
                "embedding_model": ai.get_embedder().model,
                "database": database.rsplit("/", 1)[1],
                "started_at": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            }
        }
        if args.only != "agent" and search_cases:
            log(f"Search: {len(search_cases)} queries ...")
            report["search"] = await eval_search(search_cases)
        if args.only != "search" and agent_cases:
            log(f"Agent: {len(agent_cases)} prompts ...")
            report["agent"] = await eval_agent(agent_cases, place_names)
        return report
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    base = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://app:app@localhost:5432/bdvisual"
    )
    database = args.database_url or eval_database_url(base)
    # Must be set before the app (its settings and engine) is imported.
    os.environ["DATABASE_URL"] = database
    os.environ["AI_ENABLED"] = "true"
    os.environ["AI_WORKER_ENABLED"] = "false"

    log(f"Preparing {database.rsplit('/', 1)[1]} ...")
    prepare_database(database)
    report = asyncio.run(run(args, database))

    args.out.mkdir(parents=True, exist_ok=True)
    stem = args.out / f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{args.provider}"
    stem.with_suffix(".json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str)
    )
    text = markdown(report)
    stem.with_suffix(".md").write_text(text)
    print(text)
    log(f"Wrote {stem}.json and {stem}.md")


if __name__ == "__main__":
    main()
