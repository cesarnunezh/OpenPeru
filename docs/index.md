# OpenCongress

Welcome to our documentation.

**OpenCongress** is an open source civic technology project that transforms fragmented and unstructured legislative information from the Peruvian Congress into structured data that can be easily analyzed, consumed and understood.

Its goal is to make Congress more transparent and understandable for citizens, journalists, researchers, and civil society organizations.

The project aims to improve transparency and accountability by helping people understand how Congress works: who proposes laws, how representatives vote, how parties behave, and how legislation evolves.


## Getting Started

### Development Setup

1. **Install UV**  
   Follow instructions from the official docs:  
   https://docs.astral.sh/uv/getting-started/installation/

2. **Clone the repository**  
   ```bash
   git clone https://github.com/openperu2026/dev-opencongress.git
   cd dev-opencongress
   ```

3. **Synchronize the virtual environment.**
    ```bash
    uv sync
    ```

    Scraper developers should also install the Playwright browser binary
    documented in `backend/scrapers/README.md`.

4. **Activate the environment**
    ```bash
    source .venv/bin/activate
    ```

5. **Install Git hooks (IMPORTANT)**
    We use pre-commit to enforce code quality and workflow rules.
    ```bash
    pre-commit install
    pre-commit install --hook-type pre-push
    ```

### Repository Structure

The repository is organized into modular components for data collection, processing, and testing:

```
openperu/
├── backend/
│   ├── cli/            # Command line interface for pipelines
│   ├── core/           # Shared configuration, utilities, logging
│   ├── database/       # Raw and processed database models
│   ├── process/        # Data cleaning and standardization
│   └── scrapers/       # Data collection from Congress websites
│
├── data/
│   ├── raw/            # Raw scraped data - Not available in GitHub
│   └── processed/      # Clean structured datasets - Not available in GitHub
│
├── draft_notebooks/    # Exploration and experimentation
├── logs/               # Pipeline and scraper logs
└── tests/
    ├── database/       # Tests for database models
    ├── process/        # Data processing tests
    └── scrapers/       # Scraper tests
```

Each major submodule includes its own README with more detailed documentation.

---

### Development Workflow
We follow a GitFlow branching model. For detailed rules, go [here](./branch_model.md).

*Our branches*

- `main`: Production-ready code only. This branch always reflects the current stable release.
- `dev`: Integration branch for ongoing development. All completed features are merged here before a `release`.
- `feature/*`: New feature development. Branch from `dev` and merge back into `dev` when complete.
- `release/*`: Release preparation and stabilization (e.g., bug fixes, final testing). Branch from `dev`, then merge into both `main` and `dev`.
- `hotfix/*`: Emergency fixes for production issues. Branch from `main`, then merge into both `main` and `dev`.

---

### Where to Go Next
- [Architecture](./architecture.md): Overview of the system design, including scraping pipelines, raw and processed databases, processing layers, and future applications.
- [GitFlow Model](./branch_model.md): 
- [Data Model](./data_model.md): Documentation of the main entities and relationships such as bills, motions, votes, congress members, committees, and political organizations.
- [Technical decisions](./tech_decisions.md): Documentation of the major technical decisions made in this project, including the rationale behind each choice. Serve as a reference for current and future contributors to understand why the project is built the way it is.

---

## Contributing

Contributions, feedback, and ideas are welcome.

See [Contributing](./contribute.md)
