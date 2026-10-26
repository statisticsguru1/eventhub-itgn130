# Requirements and traceability

## Authority and scope

The official source is “ITGN130 Group Project Fall 2026 27 EventHub.docx”, supplied
for Milestone 2.1. References below use its section headings and paragraph numbers
in document.xml (P62, for example); these are reference locators, not printed
section numbers. Assignment mandates take precedence over project decisions.
Approved project policies and the Milestone 2.3 single-file persistence contract
are in business_rules.md. No application features are implemented.

## Requirement-to-module-to-test mapping

All tests below are PLANNED, not existing evidence. Test IDs identify scenario
groups, not implemented methods. Existing tests/test_imports.py contains four
parameterized import/path checks only; it proves no business behavior.

| ID | Requirement and source | Owners | Planned test file / scenarios |
| --- | --- | --- | --- |
| REQ-01 | Add event with unique ID, title, date, venue, capacity, status (Functional requirements P63) | events, main | test_events.py / T01: valid creation, all fields, unique ID, invalid input unchanged |
| REQ-02 | List events (P63); project lookup and deterministic ordering | events, main | test_events.py / T02: empty/list/lookup, cancelled visibility, date then ID ordering |
| REQ-03 | Edit events (P63); approved capacity policies | events, bookings, main | test_events.py / T03: fields, immutable IDs/status, cancelled edit rejected, invalid edit unchanged; test_bookings.py: capacity changes and final returned snapshot after promotion |
| REQ-04 | Cancel events with status (P63); approved retention and cleanup | events, bookings, main | test_events.py / T04: active to cancelled, retained event, bookings/queue removed, repeated no-op, unrelated event unchanged |
| REQ-05 | Keyword or date search with confirmed/waiting counts (P67) | events, bookings, main | test_events.py / T05: title/venue, case, blank, exact/invalid date, no match, counts, cancelled results |
| REQ-06 | Register with unique student ID and name (P64) | bookings | test_bookings.py / T06: normal registration, leading zeros, required identity, missing/cancelled event |
| REQ-07 | Prevent same-event duplicate registration (P64) | bookings, storage | test_bookings.py / T07: trimmed ID, case sensitivity, confirmed/waiting duplicates, different events, re-registration |
| REQ-08 | Capacity before confirmation (P65); positive integer and no demotion policies | events, bookings | test_bookings.py / T08: last seat, overflow, bool/zero/negative/fraction rejection, reduction boundary |
| REQ-09 | FIFO overflow waiting list (P65) | bookings, storage | test_bookings.py / T09: multiple entrants, middle removal, no queue jumping; test_storage.py: order round trip |
| REQ-10 | Cancel registration (P66) | bookings | test_bookings.py / T10: confirmed/waiting/unknown cancellation, re-registration |
| REQ-11 | Automatically promote first waiting student after cancellation (P66); approved increase promotion | bookings, main | test_bookings.py / T11: head, empty queue, multiple seats on increase, no cancelled-event promotion |
| REQ-12 | Report total events, confirmed registrations, available seats, most registrations (P68); approved confirmed-only/tie interpretation | bookings, main | test_reports.py / T12: formulas, ties, zero registrations, cancelled events, one student at multiple events |
| REQ-13 | Save events, registrations, queues to JSON (P69) | storage, main | test_storage.py / T13: eventhub.json round trip, candidate/readback validation, temporary-write/replacement failures preserve old bytes, post-commit cleanup warning |
| REQ-14 | Reload at startup (P69) | storage, main | test_storage.py / T14: valid snapshot, missing first-run file, malformed/unreadable/incompatible snapshot, interruption before/after replacement |
| REQ-15 | Validate IDs, dates, menu selections, capacities (P70); approved field/state invariants | all modules | test_validation.py / T15: exact date/calendar, types, identities, references, status, duplicate JSON keys, unexpected fields, invalid stored records, no partial mutation |
| REQ-16 | Invalid input and missing/damaged files handled without crashing (P70) | main, storage | test_errors.py / T16: clear errors, reprompt/controlled stop, original data preserved, save failures and separate post-commit cleanup warnings |
| REQ-17 | Python 3.10+, functions, readable names, PEP 8, brief comments, standard libraries where possible (Objective P58; Non-functional P73–75) | all modules | test_project.py / T17: compatibility/imports; Ruff; manual functions/loops/strings/lists/dicts/comments review |
| REQ-18 | Demonstrate normal registration, full capacity/waiting, cancellation/promotion (P71); rubric edge-case evidence | tests, documentation | test_integration.py / T18: three compulsory scenarios, persistence restart; screenshot/result review |
| REQ-19 | Repeating console menu until Exit (P62) | main | test_menu.py / T19: multiple actions, invalid choice recovery, clean Exit |
| REQ-20 | Original nonsensitive sample data and portable submitted program/instructions (P76–77; Deliverables P83) | storage, README, sample data | test_project.py / T20: clean-directory run; manual synthetic sample and package inventory review |

## Mandates versus project choices

The assignment requires student ID/name, event status, cancellation, keyword/date
search, counts, reports, JSON persistence, and the three demonstrations. It does
not prescribe status names, identity normalization, exact date format, report tie
handling, UUIDs, test framework, or safe-save protocol. Milestone 2.3 approves
one authoritative eventhub.json containing schema_version, events, and bookings;
the starter file layout is guidance, not an exclusive requirement. Prohibiting
edits to cancelled events is an approved project policy, not an assignment mandate. Approved choices are
recorded separately in business_rules.md and data_model.md.

The application runtime will use the standard library. pytest and Ruff remain
development tools; this is a project choice consistent with the assignment's
“standard libraries where possible”, not an assignment ban on external tools.
Databases, web frameworks, and graphical interfaces are optional in the assignment
and excluded from this project's initial scope.

## Integration and submission evidence

Planned integration tests cover create/register/save/reload; full event with two
waiting students/cancel/promote/reload; event cancellation/search/report/reload;
and pre-commit failed save with unchanged file bytes/active state. Planned storage
tests include duplicate keys at every JSON object level, unexpected fields and
invalid records, first-save failure preserving absence, temporary-file failures,
failed replacement, leftover temporary artifacts, and post-commit warning behavior.
A restart after replacement must load the committed candidate even if success
was never acknowledged. No application tests have been implemented here.

Non-code deliverables, group responsibilities, screenshots, and presentation
requirements are tracked in submission_checklist.md. Passing automated tests does
not establish submission completeness or individual understanding.
