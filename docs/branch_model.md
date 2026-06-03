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


## Branch Protection Rules
Apply these settings in GitHub repository settings:

- Protect `main` and `dev`
- Require pull request reviews before merging (minimum 1 approval)
- Require status checks to pass (Jenkins)
- Require branches to be up to date before merging
- Restrict force pushes
- Disallow direct pushes

## Branch Lifecycle example 
This is an example of how the Git Flow Branching model will work on our project
```mermaid
%%{init: {
  "theme": "base",
  "themeVariables": {
    "git0": "#009dff",
    "git1": "#d2aeff",
    "git2": "#b0ffea",
    "git3": "#ffd1ac",
    "git4": "#ff7272",
    "gitInv0": "#000000",
    "gitInv1": "#ffffff",
    "gitInv2": "#000000",
    "gitInv3": "#000000",
    "gitInv4": "#000000",
    "primaryColor": "#161b22",
    "primaryTextColor": "#e6edf3",
    "primaryBorderColor": "#30363d",
    "lineColor": "#8b949e",
    "background": "#0d1117"
  }
}}%%

gitGraph
    commit tag:"v0.1"

    branch dev
    checkout dev
    commit

    branch feature/login
    checkout feature/login
    commit
    commit
    checkout dev
    merge feature/login

    branch release/0.2
    checkout release/0.2
    commit
    checkout main
    merge release/0.2 tag:"v0.2"
    checkout dev
    merge release/0.2

    checkout main
    branch hotfix/patch
    checkout hotfix/patch
    commit
    checkout main
    merge hotfix/patch tag:"v1.0"
    checkout dev
    merge hotfix/patch

```

