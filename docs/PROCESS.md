# Process

How work moves from idea to `main`.

## Planning

- `PLAN.md` holds the phased roadmap. Pick work from the current phase.
- `STATUS.md` says what is true right now. Update it in the same PR that
  changes it.
- Big or ambiguous items get a short write-up in `SPEC.md` (what changes in
  behaviour) before code.

## Branches and commits

- `main` is always green and releasable. Work on a branch:
  `feat/<topic>`, `fix/<topic>`, `docs/<topic>`, `chore/<topic>`.
- Conventional Commits, imperative, lower case after the type:
  `feat: pace benchmark against last year`, `fix: ...`, `docs: ...`,
  `refactor: ...`, `ci: ...`, `chore: ...`.
- One logical change per commit; the message says why when it isn't obvious.

## Pull requests

- Open a PR into `main`; CI (GitHub Actions) runs `uv sync --frozen`,
  `ruff check .` and `pytest -q`. Both must pass.
- PR description: what changed, why, how it was verified (tests + any live
  run), and any doc updated (STATUS/SPEC/README).
- Changes to prompts, tools or agent routing: run `python -m
  revenue_analyst.evals` with a real key and paste the pass/fail summary.
- Changes to pricing logic: include before/after review outcomes on the mock
  windows (as in the last-year pace change).

## Definition of done

- [ ] Tests added/updated; `uv run pytest` and `uv run ruff check .` pass.
- [ ] Rules in CODE_STANDARDS.md respected (or the exception is explained).
- [ ] README / SPEC / STATUS updated if behaviour or setup changed.
- [ ] Verified in the running app when it touches the UI or API.
- [ ] No secrets, no `.env`, no `.state/` committed.

## Learning notes

The project is also a learning journey: notable stages get a note in
`docs/notes/` — what was built, what was learned, what hurt.

## Releases

- Semantic versioning in `pyproject.toml` (`version`).
- Release commit: `chore: release X.Y.Z — <one-line summary>`, then tag
  `vX.Y.Z` on `main`.
- Breaking API or config changes bump the major and are listed in the
  release commit body.

## Safety rules for pricing

- No code path publishes rates without an explicit human approval.
- Changing a rate bound, threshold or tolerance is a reviewed PR with tests —
  never a hot edit.
