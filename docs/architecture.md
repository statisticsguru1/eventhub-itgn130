# EventHub architecture and public contracts

## Scope and ownership

Retain four function-based Python modules; no classes, frameworks, or databases.
The assignment's Quick starter outline P90–93 supports this organization. All
interfaces below are PLANNED, not implemented. Approved business policies are in
business_rules.md; single-file persistence is approved through Milestone 2.3.
Use pytest/Ruff for development and the standard library for application runtime.

| Module | Responsibility |
| --- | --- |
| main.py | Repeating console menu until Exit, input/output, conversions, startup loading, candidate orchestration, persistence, user-facing errors |
| events.py | Event creation/validation/edits/cancellation status, keyword/date search and ordering |
| bookings.py | Student identity, registration, duplicates, capacity checks, queues, promotion, registration cancellation, reports |
| storage.py | JSON serialization, complete schema/invariant validation, loading, single-file loading/saving and controlled storage errors |

main imports all three modules; bookings may call events.get_event. events never
imports bookings or main. storage imports neither domain module; its cross-record
validation checks the documented invariants. Domain modules do no terminal or file
I/O. Main composes complete operations; do not duplicate domain rules in menu code.

## Common contracts

State means the plain dictionary in data_model.md. Read operations never mutate and
return independent nested copies. Mutators operate only on a candidate supplied by
main, validate inputs before mutation, and never persist. Invalid values/types or
policy violations raise ValueError; missing event/booking IDs raise KeyError.
These expected errors leave active state unchanged because candidate is discarded.
Storage OSError and decoding/validation ValueError are translated into clear errors
by main; do not catch unexpected programming errors as if they were valid input.

| Owner / planned interface | Inputs, outputs, validation and mutation |
| --- | --- |
| events.validate_event(fields: dict) -> None | Validate exact required fields/types/date/capacity/status; no mutation; ValueError |
| events.create_event(candidate: dict, title: str, date: str, venue: str, capacity: int) -> dict | Trim/validate; allocate unique string ID; insert active event with empty queue; return independent event copy |
| events.get_event(state: dict, event_id: str) -> dict | Validate nonempty ID; return independent copy, including queue; KeyError if absent |
| events.list_events(state: dict) -> list[dict] | Return independent event copies sorted by date then ID; include cancelled |
| events.update_event(candidate: dict, event_id: str, changes: dict) -> None | Active events only; allow title/date/venue/capacity; reject unknown or immutable fields and below-attendance capacity; mutate validated fields; orchestration-only helper, no intermediate snapshot returned; main coordinates promotion and obtains final copy |
| events.cancel_event(candidate: dict, event_id: str) -> bool | Change active to cancelled; true if changed, false if already cancelled; main must coordinate booking cleanup before validation/save |
| events.search_by_keyword(state: dict, query: str) -> list[dict] | Trim/case-fold title-or-venue substring search; blank lists all; return sorted copies; ValueError for non-string |
| events.search_by_date(state: dict, date: str) -> list[dict] | Exact canonical real date; return sorted copies; ValueError for invalid date |
| bookings.register_participant(candidate: dict, event_id: str, student_id: str, student_name: str) -> dict | Validate active event, identity, same-event duplicates; confirm or append FIFO; return independent new booking copy |
| bookings.cancel_registration(candidate: dict, booking_id: str) -> dict | Remove booking and queue entry as appropriate; automatically promote head for confirmed cancellation; return cancelled_booking_id and promoted_booking_ids list |
| bookings.fill_available_seats(candidate: dict, event_id: str) -> list[str] | Active event only; promote queue heads until full/empty; return promoted IDs in order; ValueError for cancelled event |
| bookings.remove_event_registrations(candidate: dict, event_id: str) -> list[str] | Verify event exists; remove all associated bookings and clear queue without promotion; return removed IDs; internal orchestration helper |
| bookings.event_counts(state: dict, event_id: str) -> dict | Return confirmed_count and waiting_count from bookings without mutation |
| bookings.summary_report(state: dict) -> dict | Return totals/leaders described in data_model.md; no mutation; valid-state precondition |
| storage.validate_state(state: dict) -> None | Validate full schema, dates, student identities, references, queues, capacity/status invariants; no repair/mutation; ValueError |
| storage.load_state(data_dir: Path) -> dict | Read data_dir/eventhub.json and validate complete snapshot; missing first-run file returns empty state; malformed/incompatible data raises descriptive ValueError, unreadable data OSError; no mutation or automatic repair |
| storage.save_state(candidate: dict, data_dir: Path) -> None | Validate candidate and temporary readback, then os.replace into data_dir/eventhub.json; return after commit; pre-commit OSError/ValueError leaves old file unchanged; never mutate candidate; post-commit cleanup warnings cannot become failed-save errors |
| main.main() -> None | Resolve data directory relative to application root; load before menu; translate damaged/unreadable storage errors into controlled stop without overwriting data |
| main.run_menu(state: dict, data_dir: Path) -> None | Own active state locally; repeat choices until Exit; convert input, call operation helpers, display results; invalid input reprompts |
| main.apply_change(state: dict, data_dir: Path, action: str, arguments: dict) -> tuple[dict, dict] | Build deep-copy candidate; dispatch fixed allowlisted action, validate/save, return new state and result; errors propagate to menu; input state untouched |

## Complete operation sequencing

main.apply_change owns the following coordination and is the only path for
persisted domain mutations. Fixed action dispatch is simple conditional logic,
not a plugin framework. Mutation errors discard candidate before any save.

- Ordinary registration/edit/cancellation: deepcopy active state, invoke mutator,
  validate complete candidate, save, then return candidate/result. Menu rebinds
  its local active state only after successful return and then displays success.
- Capacity edit: events.update_event rejects below-confirmed capacity. Main then
  calls bookings.fill_available_seats before full validation/save. Only AFTER all promotions, main obtains an independent
  final event snapshot with events.get_event. Return result containing event and
  promoted_booking_ids only after successful save. No intermediate state is exposed.
  Any pre-commit failure discards the entire candidate.
- Event cancellation: events.cancel_event sets status; if changed, main calls
  bookings.remove_event_registrations, then obtains the final event copy and validates/saves once. Return event and
  removed_booking_ids after commit. Intermediate
  cancelled-with-bookings state stays private. Repeated cancellation returns the
  original state with a no-op message and performs no save.
- Search: main obtains sorted event copies from events and attaches counts from
  bookings.event_counts before displaying all required fields. Read-only actions
  do not save.

The cancellation and capacity helpers are orchestration-only: callers must not
save their incomplete intermediate states. main.apply_change builds all result
snapshots before persistence, using the final coordinated candidate. It returns
(new_state, result); capacity result has event and promoted_booking_ids, event
cancellation result has event and removed_booking_ids (empty for a no-op).

A failed validation, temporary write, or replacement leaves the authoritative file
and active state unchanged; menu reports the error. Successful os.replace is the
logical commit point. No fallible required save operation follows it. Main adopts
the candidate immediately upon successful save return, before success display.
Post-commit cleanup is best-effort and cannot turn a committed save into an ordinary
failed save. Crash after replacement may commit without acknowledgement. Full
limits and planned failure tests are in business_rules.md.

## Planned verification

See requirements.md for REQ-01–20 and test mappings. Existing import checks do not
exercise these contracts. Planned unit tests use pytest with temporary paths and
standard-library mocking; integration tests cover menu actions and persistence
restart. Explicit tests cover duplicate JSON keys, unexpected fields, invalid
stored records, pre-commit failures, and post-commit cleanup warnings.
No application or test implementation belongs to this milestone.
