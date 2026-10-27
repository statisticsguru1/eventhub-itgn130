# Final application architecture

EventHub uses four production modules, ordinary functions, dictionaries, lists,
and explicit control flow. There are no service/controller classes, generic
transaction dispatcher, database, or additional production modules.

| Module | Responsibility and dependencies |
| --- | --- |
| `main.py` | Startup, console input/output, mutation orchestration, read/search views and reports; imports all three domain/storage modules |
| `events.py` | Event validation, creation, editing, cancellation and ordered searches; no booking or persistence dependencies |
| `bookings.py` | Registration, cancellation, FIFO queue preflight/promotion and counts; uses event lookup, never persists |
| `storage.py` | Complete-state validation, JSON loading and atomic save; independent of application/domain modules |

## Application state and persistence boundary

`main()` loads `storage.load_state(DEFAULT_DATA_DIR)` once. `DEFAULT_DATA_DIR` is
`Path(__file__).resolve().parent / "data"`. Importing any module performs no startup
loading, prompting, or saving. The executable guard calls `main()` only when run.

Each mutating application function follows:

1. `candidate = deepcopy(state)`.
2. Complete all domain work on that isolated candidate.
3. Prepare independent result records, including any required lookups.
4. Call `storage.save_state(candidate, data_dir)`.
5. Return `(candidate, result)` only after save succeeds.

`run_menu()` immediately assigns `state = new_state` after a successful operation,
before displaying success. An exception leaves the previous binding unchanged.
No helper adopts by mutating the caller's dictionary. Expected `ValueError`,
`KeyError`, and `OSError` propagate from application functions; UI boundaries show
controlled errors. Unexpected programming errors are not disguised as input errors.

## Five mutation operations

All signatures return `tuple[dict, dict]` and accept `state: dict, data_dir: Path`
as their first arguments.

| Function / remaining arguments | Completion and exact result keys |
| --- | --- |
| `create_event_operation(title: str, date: str, venue: str, capacity: int)` | Create through events, save; `event` |
| `update_event_operation(event_id: str, changes: dict)` | Validate through events; capacity edits derive `confirmed_count` via bookings and always call `fill_available_seats`; obtain final snapshot after promotion; `changed`, `event`, `promoted_booking_ids` |
| `cancel_event_operation(event_id: str)` | Cancel status first, then remove all event registrations/queue; `changed`, `event`, `removed_booking_ids` |
| `register_participant_operation(event_id: str, student_id: str, student_name: str)` | Booking domain chooses confirmed/waiting, then save; `booking` |
| `cancel_registration_operation(event_id: str, student_id: str)` | Resolve registration on candidate, retain previous snapshot, cancel by internal booking ID, resolve promoted records before saving; `cancelled_booking`, `promoted_bookings` |

Result event/booking dictionaries and mutable lists are independent of returned
state. Repeated event cancellation skips cleanup/save and returns original state.
Empty or normalized-equal active edits skip save only after domain validation and
completion; cancelled edits and invalid supplied values still fail. No whole-state
diff framework is used.

An event capacity change can temporarily leave vacancies with waiters. The update
operation fills them FIFO before saving. Event cancellation temporarily leaves
bookings attached to a cancelled event; cleanup requires cancelled status and
removes bookings without promotion before save. Neither intermediate is persisted.

## Four read/report functions

- `list_events_view(state: dict) -> list[dict]`
- `search_events_by_keyword_view(state: dict, query: str) -> list[dict]`
- `search_events_by_date_view(state: dict, date: str) -> list[dict]`
- `summary_report(state: dict) -> dict`

Views delegate ordering/matching/validation to event readers. Private `_event_view`
obtains booking counts and creates exactly eight user-facing fields, omitting the
internal queue. Reports combine ordered events with counts once per active event.
Exact shapes/formulas are in [data_model.md](data_model.md). These functions expect
completed valid state, never save, never repair queues, and do not validate the
whole state again. Returned dictionaries are fresh.

## Domain and storage interfaces

Events exposes `validate_event`, `create_event`, `get_event`, `list_events`,
`update_event`, `cancel_event`, `search_by_keyword`, and `search_by_date`.
`update_event(candidate, event_id, changes, *, confirmed_count=None)` requires the
booking-derived count for capacity edits and returns no event snapshot.
`cancel_event` returns whether status changed; it does not remove bookings.

Bookings exposes `register_participant`, `cancel_registration`,
`fill_available_seats`, `remove_event_registrations`, `event_counts`, `get_booking`,
and `find_registration`. Counts describe actual records, including intentional
cross-module intermediates. Booking readers return independent copies.

Storage exposes `empty_state`, `validate_state`, `load_state`, and `save_state`.
Save itself validates the complete candidate; orchestration does not redundantly
validate immediately beforehand. It writes a sibling temporary JSON snapshot,
flushes/closes it, reloads/validates/compares it, then commits with `os.replace`.
Pre-commit failures preserve previous authority. Best-effort temporary cleanup
warnings after replacement do not turn a committed save into failure. A crash can
commit without acknowledgement; power-loss durability and concurrent writers are
not guaranteed. One local writer is supported.

## Console and startup

`main() -> None` loads state, stops on expected unsafe-load errors, then invokes
`run_menu(state: dict, data_dir: Path) -> None`. A genuine absent file starts empty;
missing authority with abandoned temporary snapshots requires investigation.
Corrupt/invalid files are not overwritten. EOF/KeyboardInterrupt ends the session
with a concise message.

The explicit repeating nine-option menu provides Add, Edit, List, Search, Cancel
event, Register, Cancel registration, Report, and Exit. Search repeats Keyword,
Date, Back. Private helpers collect optional edits, convert capacity, display
views/reports, and show expected errors. Student IDs stay textual. Booking UUIDs
and raw queues are not displayed; the known internal booking-ID allocation
collision receives a narrow friendly console message. Reads and Exit do not save.

## Evidence

`tests/test_main.py` covers application isolation, completion, no-ops, persistence,
result independence and read/report arithmetic. `tests/test_menu.py` covers startup,
console dispatch/errors/state adoption and a real persisted FIFO demonstration.
Domain and storage suites cover their own contracts and failure atomicity.
