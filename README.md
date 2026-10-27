# EventHub

EventHub is a Python console application developed for ITGN130 Programming in
Python. It supports event creation and management, participant registration,
capacity enforcement, FIFO waiting lists, automatic promotion, keyword/date
search, summary reporting, and JSON persistence.

## Requirements and running

Python **3.10+** is required. The application uses only the Python standard
library; no package installation or internet connection is needed to run it.
Download the project, open a terminal in its directory, and run:

```sh
python main.py
```

On Windows, `py main.py` is an alternative when the Python launcher is installed.
Runtime data is stored in `data/eventhub.json` beside the source files, regardless
of the terminal's working directory. A genuine first run starts with an empty
dataset. The data directory/file is created on a successful mutation; simply
starting and exiting does not create it. Successful changes are saved immediately.
Reads and Exit do not save.

If saved data is damaged, invalid, or unsafe to initialize, startup displays an
error and stops without replacing it. Preserve the file for investigation rather
than deleting it to bypass the error. Missing authority with abandoned temporary
snapshots also requires review.

## Menu

1. Add event
2. Edit event
3. List events
4. Search events
5. Cancel event
6. Register participant
7. Cancel registration
8. View summary report
9. Exit

Search opens a submenu: **1. Search by keyword**, **2. Search by date**,
**3. Back**. Keyword search matches title or venue, ignores case, and accepts a
blank query for all events. Date search matches an exact `YYYY-MM-DD` date.
List/search show event ID, title, date, venue, capacity, status, confirmed count,
and waiting count. Internal booking IDs are not displayed.

## Important rules

- Events receive generated unique IDs. Use the displayed event ID in later actions.
- Dates must be real calendar dates in `YYYY-MM-DD`; past dates are permitted.
- Capacity must be a positive whole number. It cannot fall below confirmed attendance.
- Student IDs are text: leading zeros and case are preserved. Surrounding whitespace
  is trimmed from student IDs/names and event titles/venues. ID comparison is case-sensitive.
- A student cannot register twice for the same event, including while waiting,
  but may register for different events. Re-registration after cancellation is allowed.
- Additional participants join a FIFO waiting list when an event is full.
- Cancelling a confirmed registration promotes the first waiter; cancelling a
  waiting registration does not promote anyone. Increasing capacity promotes as
  many FIFO waiters as the new seats permit.
- Cancelled events remain visible, cannot be edited or accept registrations, and
  cannot be reactivated. Event cancellation removes its registrations and queue.
- In Edit, Enter alone keeps a field; an entirely blank edit is a validated no-op.

The report includes total, active, and cancelled events; confirmed and waiting
registrations; available seats; and most-registered event(s). Registration totals
and available seats concern active events only. Seats equal capacity minus
confirmed registrations. All positive confirmed-count ties are shown; there is
no leader when nobody is confirmed. These include the assignment-required metrics.

## Project structure

| Location | Responsibility |
| --- | --- |
| `main.py` | Application orchestration, read/report composition, console UI, startup |
| `events.py` | Event validation and event-domain operations |
| `bookings.py` | Registration, cancellation, waiting lists, promotion |
| `storage.py` | JSON loading, complete-state validation, atomic saving |
| `tests/` | Domain, storage, application, console, and integration tests |
| `docs/` | Final architecture, requirements, schema, rules, submission checklist |
| `samples/eventhub.json` | Fictional sample snapshot; never automatically loaded |

## Sample data and a short demonstration

The sample contains three fictional events: an active capacity-three workshop
with one confirmed participant; a full capacity-one workshop with one confirmed
participant and two FIFO waiters; and a retained cancelled event without bookings.
All participant names and student IDs are invented demonstration values.

To use it, close EventHub first. If `data/eventhub.json` contains needed data,
**back it up or move it to a safe location before proceeding**. Create the `data`
folder if necessary, then copy `samples/eventhub.json` into that folder, retaining
its filename `eventhub.json`. A file manager works on Windows, macOS, or Linux.
Do not overwrite existing data blindly. The application continues to load only
`data/eventhub.json`; it never loads `samples/` automatically.

Run EventHub, use List and Report, then cancel `STU002` from the full workshop
(use its listed event ID). `STU003` is promoted before `STU004`. Exit and restart
to observe the saved result. To demonstrate normal registration, add fictional
`STU005 / Ellis Demo` to the capacity-three workshop. Work on the runtime copy;
the supplied sample remains a reusable starting point.

## Development and verification

Optional development tools are installed separately from runtime requirements:

```sh
python -m venv .venv
# Activate .venv using your platform's virtual-environment instructions.
python -m pip install -r requirements-dev.txt
pytest
ruff check .
ruff format --check .
```

Finalization verification: **579 tests passed under Python 3.12.14**, Ruff lint and
formatting checks passed. Python 3.10 syntax compatibility was checked separately;
this is not a claim of local Python 3.10 runtime execution. CI is configured for
Python 3.10. The application supports one local writer; concurrent writers and
power-loss durability are outside its guarantees.

## Submission status

Application implementation and automated tests are complete. The final PDF,
PPTX, screenshot evidence, truthful group contribution record, rehearsal, ZIP,
and Moodle submission remain separate deliverables; see
[the submission checklist](docs/submission_checklist.md).
The assignment filename references Fall 2026/27, while its internal heading says
Academic Year 2025–26. The deadline is on Moodle; confirm the year and schedule
with Moodle/the instructor rather than inferring a date.
