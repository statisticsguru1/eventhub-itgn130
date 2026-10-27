# Requirements and traceability

## Authority and implementation status

The official source is `ITGN130 Group Project Fall 2026 27 EventHub.docx`.
Paragraph locators below refer to `word/document.xml`, including table paragraphs,
not printed section numbers. The application is functionally complete through
Milestone 3.6. This table maps requirements to existing implementation and tests;
automated evidence does not establish completion of the report or live presentation.

Test paths in the table are relative to `tests/`. Scenario descriptions identify
actual coverage rather than invented test IDs.

| ID | Requirement / source | Implemented evidence | Existing test evidence / remaining evidence |
| --- | --- | --- | --- |
| REQ-01 | Add event with unique ID, title, date, venue, capacity, status (P63) | `events.create_event`, `main.create_event_operation`, Add menu | `test_events.py`: creation, collision, invalid inputs; `test_menu.py`: create/persist/display ID. Complete. |
| REQ-02 | List events (P63); approved date/ID order | `events.list_events`, `main.list_events_view`, List menu | `test_events.py`: ordering/copies; `test_main.py`: eight-field views; `test_menu.py`: list output. Complete. |
| REQ-03 | Edit event (P63), including capacity policy | `events.update_event`, `main.update_event_operation`, Edit menu | `test_events.py`: fields/count contract; `test_main.py`: capacity promotion/no-ops; `test_menu.py`: optional fields/promotion. Complete. |
| REQ-04 | Cancel event (P63), retain cancelled record | `events.cancel_event`, `bookings.remove_event_registrations`, `main.cancel_event_operation` | `test_bookings.py`: cleanup; `test_main.py`: completed cancellation; `test_menu.py`: cancellation/repeat. Complete. |
| REQ-05 | Keyword/date search with confirmed/waiting counts (P67) | `events.search_by_keyword`, `events.search_by_date`, main search views/submenu | `test_events.py`: matching/dates/order; `test_main.py`: enrichment/delegation; `test_menu.py`: search display/recovery. Complete. |
| REQ-06 | Registration with student ID/name (P64) | `bookings.register_participant`, `main.register_participant_operation`, Register menu | `test_bookings.py`: identity normalization; `test_menu.py`: textual leading-zero/case preservation. Complete. |
| REQ-07 | Prevent same-event duplicate (P64) | Booking duplicate check; `storage.validate_state` | `test_bookings.py`: confirmed/waiting duplicates, other events, re-registration; `test_storage.py`: duplicate identity. Complete. |
| REQ-08 | Check capacity before confirmation (P65) | Event validation/update; booking registration counts | `test_events.py`: positive capacity/reduction; `test_bookings.py`: last seat/full event; `test_menu.py`: controlled capacity errors. Complete. |
| REQ-09 | FIFO overflow waiting list (P65) | `event.waiting_list`, booking registration/preflight | `test_bookings.py`: queue order/fairness/malformed queues; `test_storage.py`: queue invariants/round trip. Complete. |
| REQ-10 | Cancel registration (P66) | `bookings.cancel_registration`, `main.cancel_registration_operation`, event/student menu prompts | `test_bookings.py`: waiting/confirmed/unknown; `test_main.py`: persistence/result copies; `test_menu.py`: cancellation output. Complete. |
| REQ-11 | Automatically promote first waiter (P66) | Booking cancellation; `fill_available_seats` for capacity increases | `test_bookings.py`: FIFO/atomicity; `test_main.py`: cross-module promotion; `test_menu.py`: real console demonstration/reload. Complete. |
| REQ-12 | Total events, confirmed registrations, available seats, most registrations (P68) | `main.summary_report`, report menu/display | `test_main.py`: arithmetic, positive ties, empty/cancelled states, same student across events; `test_menu.py`: report display. Complete. |
| REQ-13 | JSON persistence for events, registrations, queues (P69) | `storage.save_state`; five main mutation operations | `test_storage.py`: validation/readback/replace/cleanup failures; `test_main.py`: saved state equals returned state. Complete. |
| REQ-14 | Reload at startup (P69) | `storage.load_state`, `main.main` | `test_storage.py`: load/first run/unsafe missing authority; `test_menu.py`: startup/reload/damaged-file preservation. Complete. |
| REQ-15 | Validate IDs, dates, menus, capacities (P70) | Domain validators, storage invariants, menu/input conversion | `test_events.py`, `test_bookings.py`, `test_storage.py`: invalid types/values/references; `test_menu.py`: invalid choices and controlled errors. Complete. |
| REQ-16 | Handle invalid input and missing/damaged files safely (P70) | Main expected-error boundaries; storage controlled rejection | `test_menu.py`: startup errors, failed save, collision sanitization; `test_storage.py`: authority preserved; `test_main.py`: caller isolation. Complete. |
| REQ-17 | Python 3.10+, functions, readable names, PEP 8, standard libraries (P58, P73–75) | Four function-based modules; standard-library runtime; Ruff target py310 | `test_imports.py`, full suite, Ruff, Python 3.10 syntax check. Local tests use 3.12.14; actual 3.10 runtime verification remains a separate check. Implemented. |
| REQ-18 | Demonstrate normal/full/waiting/cancellation/promotion (P71) | Runnable menu and persisted workflows | `test_menu.py::test_console_demonstration_register_wait_cancel_promote_reload`; final acceptance sequence passed. Automated/acceptance evidence complete; screenshots and compulsory live delivery outstanding. |
| REQ-19 | Repeat menu until Exit (P62) | `main.run_menu`, search submenu, executable guard | `test_menu.py`: invalid-choice recovery, multiple actions, Exit, EOF/interrupt. Complete. |
| REQ-20 | Original nonsensitive samples and portable submitted program/instructions (P76–77, P83) | `samples/eventhub.json`, README, source-relative data path | Sample checked through actual load/views/report and isolated console; runtime uses standard library. Repository materials complete; fresh-extraction/another-machine check and ZIP submission outstanding. |

## Mandates and approved project decisions

The assignment mandates event management, registration, capacity/FIFO waiting,
cancellation/promotion, keyword/date search with counts, reports, JSON reload,
validation, and demonstrations. Approved choices include UUID generation, canonical
dates (past dates allowed), trimmed case-sensitive textual student IDs, retained
cancelled events without reactivation, positive confirmed-only report leaders with
all ties, and one authoritative `data/eventhub.json` snapshot.

The starter outline's `events.json`/`bookings.json` and `README.txt` are suggestions,
not an exclusive schema or filenames. The single snapshot keeps events and queues
consistent across a commit; README.md supplies setup instructions. pytest and Ruff
are optional development tools, not application runtime dependencies. No database,
web framework, or GUI is required.

## Remaining submission evidence

The official assignment also requires one 5–10 page PDF, 10–15 slide PPTX, a
10–15 minute compulsory group presentation plus questions, identifiable truthful
contributions for up to four students, and a complete labelled ZIP via Moodle.
These are tracked separately in [submission_checklist.md](submission_checklist.md).
The filename says Fall 2026/27; the internal heading says Academic Year 2025–26.
The deadline is stated as on Moodle: confirm the year/deadline rather than guessing.
