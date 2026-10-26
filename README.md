# EventHub

ITGN130 Programming in Python group project. The scaffold contains design
documentation and development quality infrastructure. Application features are
not implemented, and no final submission artifacts have been generated.

## Constraints

Python 3.10+, standard library application code, functions, and PEP 8.
Development checks use pytest and Ruff; they are not application dependencies.

## Setup

From the repository root, using Python 3.10 or newer:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

On Windows, activate with `.venv\Scripts\activate` instead.

## Testing and code quality

Run the same checks as CI from the repository root:

```sh
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

To apply formatting locally:

```sh
python -m ruff format .
```

Ruff targets Python 3.10, uses 88-character formatting, and enables lint rules
E4, E7, E9, and F. pytest discovers tests under `tests/`. CI runs on pushes and
pull requests using Python 3.10 and installs the bounded development dependencies
from `requirements-dev.txt`.

The infrastructure test imports each placeholder module and verifies its source
path. Passing it does not establish application feature coverage.

## Project layout

- `main.py`: planned command-line interaction and startup orchestration.
- `events.py`: planned event management and searching.
- `bookings.py`: planned registration, queues, cancellation, and reports.
- `storage.py`: planned JSON loading and saving.
- `docs/requirements.md`: mandatory scope and requirement-to-test traceability.
- `docs/architecture.md`: proposed responsibilities and function interfaces.
- `docs/data_model.md`: proposed in-memory and persisted structures.
- `docs/business_rules.md`: invariants, workflows, and unresolved questions.
- `tests/`: infrastructure tests; application tests remain planned.
- `pyproject.toml`: Ruff and pytest configuration.
- `.github/workflows/ci.yml`: automated quality checks.

## Design status

The application modules contain docstrings only; running `python main.py`
currently does nothing. Review the open questions in `docs/business_rules.md`
before implementing features. The design documents retain their original
unittest proposal; this development setup adopts pytest as requested. No
application acceptance tests have been implemented yet. Verify the documented
requirements against the official assignment sheet if further instructions
become available.
