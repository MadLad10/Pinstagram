"""Scoring functions for the eval cases. Pure, so they are unit-tested."""

import math
import uuid


def first_relevant_rank(ranked: list[str], expected: set[str]) -> int | None:
    """1-based rank of the first expected item, or None if none was returned."""
    for i, item in enumerate(ranked, start=1):
        if item in expected:
            return i
    return None


def hit_at(rank: int | None, k: int) -> float:
    return 1.0 if rank is not None and rank <= k else 0.0


def reciprocal_rank(rank: int | None) -> float:
    return 0.0 if rank is None else 1.0 / rank


def percentile(values: list[float], p: float) -> float | None:
    """Nearest-rank percentile (p in 0..100)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p / 100 * len(ordered)) - 1)]


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def arg_matches(actual, accepted: list[str], place_names: dict[str, str]) -> bool:
    """An argument matches when any accepted string occurs in it, ignoring
    case. place_ids are compared by the name of the place they refer to, so a
    model that passes the id from search_places isn't penalised."""
    if actual is None:
        return False
    value = str(actual)
    try:
        value = place_names.get(str(uuid.UUID(value)), value)
    except ValueError:
        pass
    value = value.lower()
    return any(a.lower() in value for a in accepted)


def score_tool_use(
    calls: list[dict],
    expected: list[dict],
    allowed: set[str],
    place_names: dict[str, str],
) -> dict:
    """Compare one agent run's tool calls with the case's expectations.

    `calls` and `expected` are [{"name", "args"}]; expected args map each
    argument to its accepted values. By tool name: a true positive is an
    expected tool that was called, a false positive is a called tool that was
    neither expected nor in `allowed` (harmless extras, such as reading a
    place's details first), and a false negative is an expected tool that was
    never called. An expected argument counts as correct when any call of that
    tool satisfies it.
    """
    called = {c["name"] for c in calls}
    wanted = {e["name"] for e in expected}
    args_total = args_ok = 0
    wrong_args = []
    for e in expected:
        same_tool = [c for c in calls if c["name"] == e["name"]]
        for key, accepted in e.get("args", {}).items():
            args_total += 1
            if any(
                arg_matches(c["args"].get(key), accepted, place_names)
                for c in same_tool
            ):
                args_ok += 1
            else:
                got = [c["args"].get(key) for c in same_tool]
                wrong_args.append(f"{e['name']}.{key}: want {accepted}, got {got}")
    return {
        "tp": len(called & wanted),
        "fp": len(called - wanted - allowed),
        "fn": len(wanted - called),
        "args_total": args_total,
        "args_ok": args_ok,
        "missing": sorted(wanted - called),
        "unexpected": sorted(called - wanted - allowed),
        "wrong_args": wrong_args,
    }


def precision_recall(scores: list[dict]) -> tuple[float | None, float | None]:
    """Micro-averaged over all cases."""
    tp = sum(s["tp"] for s in scores)
    fp = sum(s["fp"] for s in scores)
    fn = sum(s["fn"] for s in scores)
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return precision, recall
