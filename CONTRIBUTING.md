# Contributing / Git Workflow

Quick rules so we don't step on each other tonight — kept deliberately light,
we don't have time for a heavyweight process.

## Folder ownership

Only edit inside your own folder. Need to change something outside it (e.g.
`ai-engine/data/concepts.json`)? Message the owner first — don't edit it silently.

| Folder | Owner |
|---|---|
| `ai-engine/` | Member 2 |
| `knowledge-engine/` | Member 1 |
| `frontend/` | Member 3 |

## Branches

- `main` — always working, demo-able. Nobody pushes to `main` directly.
- One branch per person:
  - `member1-knowledge-engine`
  - `member2-ai-engine`
  - `member3-frontend`

## Workflow

1. Before starting a work session, sync with `main`:

git checkout main
git pull
git checkout your-branch-name
git merge main

2. Commit often, in small chunks — not one giant commit at the end.
   Format: `type: short description`
   - `feat: add debt detection service`
   - `fix: correct mastery threshold`
   - `test: add /diagnose integration test`
   - `docs: update README`

3. Push your branch:
git push -u origin your-branch-name

   (drop `-u origin your-branch-name` after the first push — just `git push` works from then on)

4. Open a Pull Request into `main` once your part runs locally without errors.

5. Merge your own PR right away — no formal review needed tonight, we just
   want clean history and a stable `main`.

## Before every push

- [ ] Code runs locally without errors
- [ ] `git status` checked — no `.env` or API key in the list
- [ ] No leftover debug `print()` spam
- [ ] Tests pass, if this change touches tested code

## If two people accidentally touch the same file

git pull

Git will flag a conflict. Open the file, find the `<<<<<<<` markers, keep the
lines you want, delete the markers, then:

git add <the file>
git commit
git push

## Shared data

`ai-engine/data/concepts.json` is the source of truth for the concept graph.
`knowledge-engine/data/concepts.json` is a copy. If Member 2 changes the
original, ping Member 1 to re-copy it.