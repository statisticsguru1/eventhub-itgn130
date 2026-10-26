# EventHub business rules

## Authority and status

Assignment mandates are identified in requirements.md using official paragraph
references. The business policies below, including single-file storage, are approved through
Milestone 2.3. They are design contracts, not
claims of implemented behavior. The existing four-module structure is retained.

## Approved event and registration policies

1. Events contain event_id, title, date, venue, capacity, status, waiting_list.
   Create active; permit active -> cancelled. Retain cancelled event records.
   Cancellation removes every associated booking and clears the queue in one
   logical candidate-state operation. Do not promote during event cancellation.
   Repeated cancellation is a clear no-op. No reactivation or permanent deletion
   in the initial scope. Editing cancelled events is explicitly prohibited in the
   initial version: this is an approved project policy, not an assignment mandate.
2. Registrations contain booking_id, event_id, student_id, student_name, status.
   Trim student IDs, preserve leading zeros, use case-sensitive comparison, and
   impose no arbitrary length restriction. Names are display attributes. Reject
   same-event duplicate IDs across confirmed and waiting statuses before mutation.
   Different events and re-registration after cancellation are allowed.
3. Capacity is a positive integer, excluding bool. Confirm only when space exists;
   otherwise append to FIFO. Reject reductions below confirmed attendance and do
   not demote. On increase, fill all vacancies from the queue in order. An active
   event cannot retain a queue while seats are available after a successful action.
4. Confirmed-registration cancellation removes the booking and promotes the queue
   head if present. Waiting-registration cancellation removes only that entry,
   preserving relative order. Missing IDs produce clear errors. Cancelled events
   prohibit registrations and promotions and retain no current bookings.
5. All dates use exact YYYY-MM-DD and real calendar validation. Permit past dates.
   Use the same rule for creation, edits, date search, and stored data.
6. Trim required title, venue, and student_name strings; reject empty values.
   Validate complete changes before mutation. Never modify immutable IDs through
   event editing. Event status changes use cancellation, not arbitrary field edits.

## Approved search and report policies

Provide separate keyword and date choices. Trim/case-fold keywords and match title
or venue substrings. Blank keyword lists all events. Date search uses a validated
exact date; invalid or blank dates produce an error. Include cancelled events with
clear status. Rows show event ID, title, date, venue, capacity, status, confirmed
count, waiting count; sort by date then event ID.

Reports count all retained events; sum confirmed registrations and available seats
across active events. Seats equal capacity minus confirmed count, without hiding
invalid state by clamping. Most registrations means most confirmed registrations;
show every tied active leader sorted by date then event ID. With no confirmed
registrations, display that fact and no arbitrary leader. Also report waiting
registrations and active/cancelled counts. Derive values from authoritative records;
cancelled events contribute zero registrations and available seats.

## Approved single-file persistence contract

The authoritative file is data/eventhub.json, resolved relative to the application
root, containing exactly schema_version, events, and bookings. Queues are stored
inside events. Assignment P69 requires JSON persistence and P70 requires safe error
handling. The starter's events.json/bookings.json layout is suggested, not exclusive;
this approved single-file decision supersedes the previous two-file proposal.

### Startup

- Missing eventhub.json on first run initializes schema_version: 1 with empty
  events and bookings dictionaries. Explain initialization; do not write until a
  successful mutation. Missing parent directory is created only when saving.
- Parse existing UTF-8 JSON with duplicate-key rejection at every object level,
  then validate the complete schema and domain invariants before returning state.
- Malformed JSON/encoding, unexpected fields, invalid records, unsupported schema,
  or unreadable files cause a clear controlled error and stop normal startup.
  Do not turn these errors into empty state or silently overwrite damaged data.
- A leftover temporary file is never authoritative and is never automatically
  loaded or promoted. If the authoritative file is absent but temporary artifacts
  suggest interruption, explain that absence and require explicit review before
  treating it as a new dataset. Do not silently discard possible unsaved data.

### Save sequence and commit point

1. Validate the entire candidate before any authoritative-file change. Main owns
   the candidate; storage never mutates it. The application must have loaded valid
   state or completed first-run initialization before allowing a mutation.
2. Create a uniquely named temporary sibling, for example eventhub-<random>.tmp,
   in the same directory/filesystem. Serialize the complete candidate as UTF-8
   JSON, close it successfully, then reopen, parse, and fully validate it. Require
   the reloaded state to equal the candidate before replacement.
3. Call os.replace(temporary_path, authoritative_path). Successful replacement is
   the logical commit point. No validation or other fallible required save step
   follows it. The previous snapshot remains authoritative until this succeeds.
4. Return success. Main adopts the candidate and then displays success. Any
   optional cleanup after replacement is best-effort; catch/report cleanup issues
   separately as warnings, never as ordinary failed saves or reasons to retain
   the old active state. Do not undo a committed replacement because of cleanup.

| Failure | Authoritative file and active state |
| --- | --- |
| Candidate validation fails | Previous file unchanged; candidate discarded; no save |
| Temporary creation/write/serialization/close/reopen/validation fails | Previous file unchanged (or remains absent on first save); candidate not adopted; clear error |
| os.replace fails before successful replacement | Previous file unchanged under supported local filesystem semantics; candidate not adopted; clear error |
| Optional temporary cleanup fails before commit | Preserve original save error and old state; warn about leftover temporary file |
| Optional cleanup fails after successful replacement | New file committed; adopt candidate and report save success with separate warning |
| Crash before replacement | Old file remains authoritative, or absent on first save; temporary artifacts may remain |
| Crash after replacement but before acknowledgement | New state committed, possibly without success message; restart loads the validated authoritative snapshot |

Before-commit errors are ValueError for serialization/validation/encoding problems
or OSError for filesystem failures. Storage translates expected JSON serialization
TypeError into a descriptive ValueError; it does not mask unrelated programming
errors. Main displays clear errors without an uncaught
traceback and retains active state. An unsuccessful save does not trigger an
automatic backup restoration. Users may preserve damaged files and repair/restore
an independently verified copy manually outside normal application startup.

### Limits and simplicity

Use one application process/writer on a local filesystem with normal replacement
semantics; concurrent writers and external edits during execution are unsupported.
There is no transaction framework, database, generation metadata, or automatic
backup system. A successful replacement is not a promise of durability against
all power failures, device loss, filesystem corruption, or network-filesystem
behavior. Acknowledgement cannot be guaranteed across a crash after commit.
No old-snapshot rollback is promised after successful replacement.

### Planned storage tests

Use pytest temporary directories and controlled filesystem failures. Test missing
first-run file, valid round trip/restart and FIFO retention; duplicate JSON keys
at root and nested levels; unexpected root/event/booking fields; invalid stored
records/types/dates/status/identity/references/queues/capacity; malformed JSON,
invalid encoding, unreadable files and incompatible schema. Test candidate rejection,
failed temporary creation/write/close/readback validation, failed replacement,
pre-commit cleanup failure, and post-commit cleanup warning. Assert old file bytes
and active state unchanged for pre-commit failures (or absence on first save).
Assert committed candidate adoption despite post-commit cleanup problems. Simulate
interruption before and after replacement and distinguish commitment from user
acknowledgement. All these tests are planned, not implemented.
