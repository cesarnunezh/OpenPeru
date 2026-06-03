# Contributing to CongresoAbierto/OpenCongress

Thank you for your interest in contributing to OpenCongress
This document explains how to set up the project, follow our workflow, and collaborate effectively.

---

# Quick Start

Clone the repository and install dependencies:

```bash
git clone https://github.com/openperu2026/dev-opencongress.git
cd dev-opencongress

# install dependencies
uv sync

# activate environment
source .venv/bin/activate

# install git hooks (required)
pre-commit install
pre-commit install --hook-type pre-push

# run checks
pre-commit run --all-files
```

We use `uv` for environment management and `pre-commit` to enforce code quality and workflow rules.

---

---

# GitFlow Workflow

We follow a GitFlow model.

## Protected branches
- `main`: production-ready code
- `dev`: integration branch

## Working branches
- `feature/*`: new features (branch from `dev`)
- `release/*`: release preparation (branch from `dev`)
- `hotfix/*`: urgent fixes (branch from `main`)

## Rules
- Do NOT commit directly to `main` or `dev`
- All changes must go through Pull Requests
- Branch naming is enforced automatically

## Example workflow

```bash
git checkout dev
git pull
git switch -c feature/my-feature

# work
git add .
git commit -m "feat: add feature"

git push origin feature/my-feature
```

---

# Pull Requests

Before opening a PR, ensure:

- Code is formatted and linted (`pre-commit`)
- All tests pass
- Documentation is updated if needed

Each PR must:
- Include a clear description of the change
- Be reviewed by at least one contributor
- Pass all CI checks

After merging:
- Delete the branch

---

# Pull Requests

Before opening a PR, ensure:

- Code is formatted and linted (`pre-commit`)
- All tests pass
- Documentation is updated if needed

Each PR must:
- Include a clear description of the change
- Be reviewed by at least one contributor
- Pass all CI checks

After merging:
- Delete the branch

---

# Continuous Integration

We use GitHub Actions to enforce:

- Code quality (Ruff)
- Unit tests (pytest)
- GitFlow rules (branch validation)

If your PR fails:

```bash
pre-commit run --all-files
uv run pytest
```

Check GitHub Actions logs for details.

---

# Decision Making

- Maintainers define overall project direction and architecture
- Contributors have autonomy over implementation details

Decisions should prioritize:
1. User needs
2. Project goals
3. Simplicity and maintainability

Major decisions should be documented in `/docs/`.

---

# Collaboration Principles

- Each feature should correspond to a GitHub Issue
- One owner per issue
- Keep communication clear and documented
- Prefer small, focused contributions

---

# Generative AI

We will use AI tools as references, but we should write our own code. AI should assist, not replace, developer judgment.
Specifically, we can ask AI tools to:

* Provide existing solutions related to features we're trying to implement when we get stuck
* Explain how a particular function works
* Help explain error messages
* Proofread documentation
* Make proper citations for AI-generated code
* Refactoring with human review
* Generate test cases

AI should never be used to support both test generation and code generation. A human should be fully responsible for either (1) making the feature work (code) or (2) making the standards of how a feature works (tests).

This is meant to provide protections against subtle architectural decisions and bugs introduced by AI, which cannot fully understand context.
