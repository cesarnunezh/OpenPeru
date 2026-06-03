# Git Flow Branching Model

## Branch Types
- `main`: Production-ready code only.
- `dev`: Integration branch for completed work.
- `feature/*`: New feature development, branched from `dev`.
- `release/*`: Release stabilization, branched from `dev`.
- `hotfix/*`: Emergency fixes, branched from `main`.

## Usage Rules
- No direct pushes to `main` or `dev`.
- All changes merge via pull requests.
- `feature/*` merges into `dev`.
- `release/*` merges into `main` and back into `dev`.
- `hotfix/*` merges into `main` and back into `dev`.

## Feature Lifecycle
1. `git checkout develop`
2. `git checkout -b feature/<short-name>`
3. Work, commit, push, open PR to `dev`.
4. Merge after checks pass.

## Release Lifecycle
1. `git checkout develop`
2. `git checkout -b release/<version>`
3. Stabilize changes and update docs.
4. Open PR to `main`.
5. Merge to `main`, tag release.
6. Merge `release/<version>` back into `dev`.

## Hotfix Lifecycle
1. `git checkout main`
2. `git checkout -b hotfix/<short-name>`
3. Fix and commit.
4. Open PR to `main`.
5. Merge to `main`, tag hotfix.
6. Merge `hotfix/<short-name>` back into `dev`.

## Branch Protection Rules (GitHub)
Apply these settings in GitHub repository settings:
- Protect `main` and `dev`
- Require pull request reviews before merging (minimum 1 approval)
- Require status checks to pass (Jenkins)
- Require branches to be up to date before merging
- Restrict force pushes
- Disallow direct pushes
