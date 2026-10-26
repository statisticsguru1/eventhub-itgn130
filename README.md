# EventHub

ITGN130 Programming in Python group project: a menu-driven event registration and
booking system. This repository currently contains design documentation, placeholder
Python modules, and development quality infrastructure. Application features and
acceptance tests are not implemented. Running python main.py currently does nothing.

## Authority and design status

The official “ITGN130 Group Project Fall 2026 27 EventHub.docx” was reconciled in
Milestone 2.1. Mandatory requirements and source references are in
[requirements](docs/requirements.md). Approved policies through Milestone 2.3 are in
[business rules](docs/business_rules.md), including the approved single-file
persistence contract. Documentation approval does not implement application code.
No final report, slides, sample JSON files, or submission ZIP are produced here.

The document filename suggests Fall 2026–27 but its internal heading says Academic
Year 2025–26. Verify this and all deadlines with the instructor/Moodle.

## Development setup

Use Python 3.10 or newer from the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

On Windows, activate with .venv\Scripts\activate instead. Application runtime
will use the standard library; pytest and Ruff are development tools, not required
application libraries. No framework, database, or GUI is planned.

Run the existing development checks from the repository root:

```sh
python -m ruff check .
python -m ruff format --check .
python -m pytest
```

CI uses Python 3.10 and these commands. Ruff targets Python 3.10, 88-character
formatting, and E4/E7/E9/F rules. tests/test_imports.py contains four parameterized
module import/path checks only. Business and integration tests in the requirements
mapping are PLANNED. No test results are claimed by this documentation revision.

## Approved intended behavior

- Events have unique ID, title, date, venue, positive capacity, active/cancelled
  status, and FIFO queue. Cancellation retains the event and removes its bookings;
  editing cancelled events, reactivation, and permanent deletion are prohibited
  in the initial scope by approved project policy.
- Register with trimmed case-sensitive student ID and name; preserve leading
  zeros. Prevent same-event duplicates across confirmed and waiting registrations.
- Enforce capacity; promote FIFO after confirmed cancellation or capacity increase;
  reject reductions below confirmed attendance and never demote.
- Validate exact YYYY-MM-DD dates, including calendar validity; permit past dates.
- Search title/venue keywords or exact dates; display status and confirmed/waiting
  counts, including cancelled events, ordered by date then event ID.
- Report retained events, active confirmed registrations and available seats, and
  all tied leaders by confirmed registrations; also show waiting and status totals.

## Layout and persistence plan

- main.py: repeating menu, input/output, orchestration and errors.
- events.py: event creation, validation, updates, cancellation and searches.
- bookings.py: student registration, capacity/FIFO, cancellation, promotion, reports.
- storage.py: JSON validation, load/save, and controlled storage errors.
- [Architecture](docs/architecture.md): planned public contracts and mutation ownership.
- [Data model](docs/data_model.md): fields, invariants, and the authoritative JSON snapshot.
- [Submission checklist](docs/submission_checklist.md): delivery/evidence requirements.
- pyproject.toml and .github/workflows/ci.yml: existing pytest/Ruff and CI settings.

The authoritative runtime file is data/eventhub.json, relative to the application
root. It contains schema_version, events, and bookings; waiting-list order stays
inside each event. Missing file on first run initializes empty state; malformed,
unreadable, or incompatible data produces a controlled error without overwriting.
Leftover temporary artifacts require review if the authoritative file is absent.

Save validates the candidate and a temporary sibling readback before os.replace.
Successful replacement commits; only then is candidate adopted. Pre-commit failure
keeps the previous file unchanged. Post-commit cleanup errors are separate warnings,
not failed saves. A crash after replacement can commit without a success message.
No automatic backup system is required, and universal power-failure durability is
not promised. The application assumes one writer on a local filesystem.

Runtime data paths are ignored; original nonsensitive sample eventhub.json must
later be included explicitly in the submission. The assignment's suggested starter
file layout is not exclusive; Milestone 2.3 approves the single authoritative file.

Final application run instructions and clean-computer validation must be completed
when the application exists. Follow the submission checklist; current import tests
are not evidence of assignment completion.
