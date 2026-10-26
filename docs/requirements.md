# Requirements and traceability

## Mandatory assignment scope

The requirements below capture the supplied assignment requirements. They do not
claim additional details from an unavailable assignment sheet. Every test is
planned, not implemented. Test identifiers refer to future test methods in the
listed files. One requirement may need multiple assertions and cases.

| ID | Required behavior or constraint | Planned module(s) | Planned test file and scenario ID |
| --- | --- | --- | --- |
| REQ-01 | Create events | events.py | test_events.py / T01: valid creation; invalid input rejected without mutation |
| REQ-02 | Read/list event details | events.py | test_events.py / T02: existing, missing, and empty event collection |
| REQ-03 | Update events | events.py | test_events.py / T03: valid update; unknown ID; invalid update leaves original intact |
| REQ-04 | Delete events | events.py | test_events.py / T04: deletion and unknown ID; associated bookings handled under reviewed policy |
| REQ-05 | Search events | events.py | test_events.py / T05: matching, nonmatching, and empty query under reviewed search policy |
| REQ-06 | Register participants for events | bookings.py | test_bookings.py / T06: registration; unknown event; invalid participant |
| REQ-07 | Prevent duplicate registrations | bookings.py | test_bookings.py / T07: repeat identity in confirmed list and waiting list; different events allowed |
| REQ-08 | Enforce event capacity | bookings.py, events.py | test_bookings.py / T08: below limit, last seat, full event; confirmed count never exceeds capacity |
| REQ-09 | Maintain FIFO waiting lists | bookings.py | test_bookings.py / T09: full event queues three participants in arrival order |
| REQ-10 | Cancel bookings | bookings.py | test_bookings.py / T10: cancel confirmed and waiting booking; missing/already cancelled booking |
| REQ-11 | Automatically promote waiting participants after cancellation | bookings.py | test_bookings.py / T11: oldest waiting participant promoted; no queue; cancelling waiting entry creates no vacancy |
| REQ-12 | Produce summary reports | bookings.py | test_reports.py / T12: empty system and multiple events; counts agree with bookings |
| REQ-13 | Persist application data as JSON | storage.py, main.py | test_storage.py / T13: save/load round trip preserves events, registrations, IDs, and FIFO order |
| REQ-14 | Load saved data at startup | storage.py, main.py | test_storage.py / T14: existing valid file loaded before menu; missing file follows reviewed policy |
| REQ-15 | Validate input | main.py, events.py, bookings.py, storage.py | test_validation.py / T15: blank text, malformed numbers, invalid capacity/date, malformed JSON/schema; no partial mutation |
| REQ-16 | Handle errors | main.py, storage.py | test_errors.py / T16: unknown IDs, bad menu input, unreadable/malformed file, failed save; reviewed recovery behavior |
| REQ-17 | Use Python 3.10+, standard libraries, functions, and PEP 8 | all modules | test_project.py / T17: syntax/import checks; manual version, imports, function-based design, and style review |
| REQ-18 | Cover required scenarios with tests | tests/ | test_project.py / T18: review coverage against T01–T17; execute unittest suite once implemented |

## Proposed design decisions (not assignment mandates)

Use a terminal menu, string IDs, dictionaries and lists, per-event participant
identity derived from normalized email, ISO dates, JSON schema versioning, and
standard-library `unittest`. Reports initially show per-event capacity, confirmed
count, waiting count, available seats, and overall totals. Search initially uses
case-insensitive title/location substring matching. These details require review;
the supplied task does not prescribe fields, menu format, report layout, or exact
search semantics.

Open policies and their affected test expectations are listed in
[business_rules.md](business_rules.md). No unresolved policy is an implemented
behavior or an approved acceptance criterion.
