# docs/

Specs for Claude Code. Read these before writing code.

## How to use this folder

When you start a session with Claude Code, point it at the relevant files for your task:

- **Starting a new feature?** → read `CLAUDE.md`, then the specific `features/<name>.md`, then `DATA_MODEL.md` and `API.md` as needed.
- **Starting fresh on the repo?** → read `CLAUDE.md`, `PROJECT.md`, `ARCHITECTURE.md`, `SETUP.md`, then `BUILD_PLAN.md` to know what to do next.
- **Changing the DB?** → update `DATA_MODEL.md` in the same commit.
- **Changing an endpoint?** → update `API.md` in the same commit.

## Index

| File | What's in it |
|---|---|
| `CLAUDE.md` | Coding conventions, repo rules, definition of done. **Claude Code reads this first.** |
| `PROJECT.md` | Product overview, user roles, MVP scope, what's deferred |
| `ARCHITECTURE.md` | System diagram, auth flow, feed algorithm, directions algorithm |
| `DATA_MODEL.md` | Every table, every column, indexes |
| `API.md` | Every endpoint with request/response shapes |
| `SETUP.md` | Local dev setup, env vars, common pitfalls |
| `BUILD_PLAN.md` | Phased build order — don't skip ahead |
| `features/auth.md` | Auth feature spec |
| `features/feed.md` | Feed feature spec |
| `features/place-details.md` | Place page + "How to Get There" |
| `features/posting.md` | Upload, compose, moderation queue |
| `features/reviews.md` | Reviews & ratings |
| `features/search-and-map.md` | Search + map view |
| `features/social.md` | Follow, like, comment, save |
| `features/admin.md` | Moderation, admin dashboard |

## Workflow tip

When prompting Claude Code, be explicit about which files to read:

> "Build the auth signup endpoint. Read `docs/CLAUDE.md`, `docs/features/auth.md`, `docs/DATA_MODEL.md` (users + email_verifications + refresh_tokens sections), and `docs/API.md` (auth section)."

This keeps context focused and prevents Claude from inventing things the docs already answer.
