# Proposed architecture

All architecture choices here are proposals. Mandatory behavior is identified by
REQ IDs in [requirements.md](requirements.md). No interfaces are implemented yet.

## Responsibilities and dependencies

`main` calls `storage`, `events`, and `bookings`. `bookings` may use event lookup
from `events`. Domain modules never import `main` or perform terminal/file I/O.
`storage` handles the complete state and does not import domain modules. Shared
structures are plain dictionaries and lists described in `data_model.md`.
Use functions, standard libraries, PEP 8 naming, and Python 3.10+ annotations.

| Module | Responsibility | Requirements |
| --- | --- | --- |
| main.py | Load at startup, menu/input conversion, display results, catch expected errors, orchestrate save | REQ-14–17 |
| events.py | Event validation, CRUD, lookup and search | REQ-01–05, REQ-08, REQ-15 |
| bookings.py | Registration identity, capacity, FIFO, cancellation/promotion, summary calculation | REQ-06–12, REQ-15 |
| storage.py | JSON serialization, schema validation, startup load and safe save | REQ-13–16 |
| tests/ | Future unittest cases and temporary storage fixtures | REQ-18 |

## Planned function interfaces

Signatures below are documentation only. `State`, `Event`, `Booking`, and
`Summary` are descriptive aliases for dictionaries, not proposed classes.
Functions return copies for read operations. Mutations validate completely before
changing state. Expected domain failures raise `ValueError` with a useful message;
unknown IDs raise `KeyError`. Main translates these into user-facing messages.

| Module | Planned signature | Result or effect |
| --- | --- | --- |
| main | `main() -> None` | Load, run menu, coordinate changes and persistence |
| main | `run_menu(state: dict, path: Path) -> None` | Present commands and handle recoverable errors |
| events | `create_event(state: dict, title: str, date: str, location: str, capacity: int) -> dict` | Add event, return event copy |
| events | `list_events(state: dict) -> list[dict]` | Return event copies in stable order |
| events | `get_event(state: dict, event_id: str) -> dict` | Return event copy or raise KeyError |
| events | `update_event(state: dict, event_id: str, changes: dict) -> dict` | Validate allowlisted fields, return updated copy |
| events | `delete_event(state: dict, event_id: str) -> None` | Remove event under reviewed booking policy |
| events | `search_events(state: dict, query: str) -> list[dict]` | Return matching event copies |
| events | `validate_event(fields: dict) -> None` | Reject invalid event fields |
| bookings | `register_participant(state: dict, event_id: str, name: str, email: str) -> dict` | Return new confirmed or waiting booking |
| bookings | `cancel_booking(state: dict, booking_id: str) -> dict` | Return cancelled ID and optional promoted ID |
| bookings | `promote_next(state: dict, event_id: str) -> str | None` | Internal helper: promote oldest eligible entry if a seat exists |
| bookings | `summary_report(state: dict) -> dict` | Return per-event metrics and totals without mutation |
| storage | `load_state(path: Path) -> dict` | Read and validate persisted state |
| storage | `save_state(state: dict, path: Path) -> None` | Serialize and replace stored snapshot |
| storage | `validate_state(state: dict) -> None` | Check schema, references, uniqueness and capacity/FIFO invariants |

## Proposed persistence flow

Load before menu interaction. For each change, work on a `copy.deepcopy` candidate,
apply the complete operation (including promotion), save it, then adopt it as the
active state. This avoids a partially applied in-memory action after a failed
save. Write a temporary sibling file and use `os.replace` after successful JSON
serialization. Keep queue changes and cancellation in one snapshot. Report a
success only once saving succeeds. Exact retry/recovery and startup failure
policies remain open; see Q04. Atomic replacement alone does not guarantee
recovery from every device/power failure.

## Planned verification

Use `unittest`, `tempfile`, and `unittest.mock` only. Domain tests work with fresh
in-memory fixtures; storage tests use temporary directories and simulated I/O
failures. An integration test covers load → register/wait → cancel/promote → save
→ reload. Review all REQ-to-T mappings before claiming assignment completion.
