# Contributing

Thanks for helping improve Synthesis Suite. This project welcomes bug reports, feature ideas, documentation fixes, tests, and code contributions.

## Development Setup

Use a local virtual environment unless you specifically prefer Conda:

```bash
npm install
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
npm run setup:backend
npm start
```

Windows PowerShell:

```powershell
npm install
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
npm run setup:backend
npm start
```

Optional Conda users can create any env name and point Synthesis Suite at it:

```bash
conda create -n synthesis python=3.11 -y
conda activate synthesis
python -m pip install -r python-backend/requirements.txt
SYNTHESIS_CONDA_ENV=synthesis npm start
```

## Before Opening a PR

Run:

```bash
npm run check:js
npm run smoke:backend:quick
```

For backend, model, chart, preprocessing, or packaging changes, also run:

```bash
npm run smoke:backend
```

## Pull Request Guidelines

- Keep changes focused and explain the user-facing behavior being changed.
- Include screenshots or short recordings for UI changes when useful.
- Add or update smoke coverage when changing backend data, chart, or model behavior.
- Do not commit generated installers, build directories, virtual environments, logs, or local `.env` files.
- Keep TypeScript source and generated JavaScript in sync by running `npm run build:ts`.

## Packaging Contributions

Synthesis Suite ships an Electron app plus a Python backend binary. That backend binary must be built on the target OS, so release packaging is handled by `.github/workflows/release.yml`.

Use local package scripts only for the platform you are currently on:

```bash
npm run build:win
npm run build:mac
npm run build:linux
```

When changing installer behavior, check the matching GitHub Actions job or test on the matching OS.

## Solving Issues (How to contribute by fixing issues)

Follow this workflow to efficiently pick up and resolve issues so maintainers can review and merge your work quickly.

- **Find an issue**: Look for issues labeled `good first issue`, `help wanted`, or `bug`. Use the issue list on GitHub or run `gh issue list --label "good first issue"` locally.
- **Comment to claim**: Post a short comment on the issue like "Taking this" so other contributors know it's being worked on. Use `gh issue comment <number> --body "Taking this"` if you prefer the CLI.
- **Reproduce & document**: Reproduce the bug locally and update the issue with reproduction steps, environment, and minimal reproduction if possible.
- **Create a branch**: Use a descriptive branch name that references the issue number, e.g. `issue/123-fix-crash-on-load`.

	```bash
	git checkout -b issue/123-fix-crash-on-load
	```

- **Make focused changes**: Keep commits small and focused. Update or add tests that cover the bug or feature. If a change touches multiple areas, split it into separate PRs when practical.
- **Update the issue**: Push progress as comments on the issue (what you've tried, blockers, ETA). If you need help from maintainers, tag them in the issue or request review early.
- **Run checks**: Before opening a PR run the project's checks:

	```bash
	npm run check:js
	npm run smoke:backend:quick
	npm run build:ts
	```

- **Open a PR**: Link the issue in the PR title or description. Use keywords to auto-close the issue when merged, e.g. `Fixes #123`.

- **PR checklist** (add this to your PR description):
	- **Related issue**: link to the issue (e.g. `Fixes #123`).
	- **Reproduction steps**: short list of how to reproduce the bug or verify the fix.
	- **Tests**: included or updated tests, or a note explaining why tests aren't applicable.
	- **Screenshots / recordings**: for UI changes.
	- **CI**: all CI checks pass locally for you.

- **Address review feedback**: Respond to review comments, update the branch, and keep the PR focused. If the change grows large, split work into follow-up issues/PRs.
- **Closing issues**: Use `Fixes #<number>` in the PR body to automatically close the issue when merged. If you cannot finish the fix, update the issue with what remains and unassign yourself.

### Triage and labeling (for maintainers/triagers)

- When triaging, add labels such as `type:bug`, `type:enhancement`, `priority:high`, and `good first issue` when appropriate.
- Add reproduction steps and an initial severity estimate to new bug reports to help contributors pick them up quickly.

Following this workflow helps contributors and maintainers collaborate efficiently and keeps issue resolution predictable and transparent.

### Current open issues (snapshot)

Below are a few current open issues you can use as examples or pick up to work on. This snapshot was captured on 2026-05-22 — check the repository's Issues page for the latest list.

- [#27](https://github.com/vectrasols/synthesis/issues/27) — Add a changelog or audit trail for cleaning actions (labels: documentation, enhancement)
- [#26](https://github.com/vectrasols/synthesis/issues/26) — Add clearer validation messages for required inputs (labels: bug, good first issue)
- [#25](https://github.com/vectrasols/synthesis/issues/25) — Add import support for previously exported models (labels: enhancement, help wanted)
- [#24](https://github.com/vectrasols/synthesis/issues/24) — Add side-by-side comparison between trained models (labels: enhancement, help wanted)
- [#23](https://github.com/vectrasols/synthesis/issues/23) — Add dataset preview and class distribution summary before training (labels: enhancement, help wanted)
- [#22](https://github.com/vectrasols/synthesis/issues/22) — Add persistent user preferences for theme and layout (labels: enhancement, good first issue)

To list issues locally with the GitHub CLI, try:

```bash
gh issue list --state open --label "good first issue"
gh issue view <number> --web
```


## Code Style

- Keep UI changes consistent with the existing Electron renderer structure.
- Keep backend behavior in service modules and expose it through FastAPI only where needed.
- Prefer deterministic samples and fixed random seeds for demos and tests.
- Prefer clear, boring code over clever abstractions.

## Security

Please report vulnerabilities privately. See [SECURITY.md](SECURITY.md).

## Conduct

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
