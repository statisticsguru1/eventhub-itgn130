# Business rules and open questions

## Mandatory assignment rules

- Event CRUD and searching must be available (REQ-01–05).
- Register participants and prevent duplicates (REQ-06–07).
- Enforce capacity; overflow joins a FIFO waiting list (REQ-08–09).
- Support booking cancellation and automatic promotion (REQ-10–11).
- Provide summary reports, JSON persistence, startup loading, validation, and
  error handling (REQ-12–16).

## Proposed operational rules

These are reviewable decisions, not claims about unspecified assignment details.

1. Trim names, titles, locations and email. Require nonempty text. Use stripped,
   case-folded email as the per-event duplicate key across confirmed and waiting
   bookings. Basic email shape validation is proposed; no external verification.
2. Register into confirmed bookings if a seat is free; otherwise append the new
   booking ID to the tail of the event waiting list. Reject a duplicate without
   changing any state. Apply this consistently after loading persisted data.
3. Cancelling a confirmed booking removes it and promotes the queue head to
   confirmed in the same operation. Cancelling a waiting booking removes its ID
   while preserving remaining order and promotes nobody. Missing/already removed
   bookings produce a clear error. An empty queue requires no promotion.
4. Search title/location with case-insensitive substrings; a blank query lists
   all events. Reports count current confirmed and waiting bookings separately.
5. Validate before mutation. Reject unknown event/booking IDs, unknown update
   fields, blank required fields, and invalid types. Main catches expected input
   and storage errors and shows actionable messages without raw tracebacks.
6. Capacity increases should fill newly available seats from the queue in FIFO
   order; this is proposed beyond the explicit cancellation promotion requirement.
   Route capacity edits through an orchestrated operation so events.py does not
   import bookings.py. Exact edit interface can be refined after review.

## Unresolved questions — review before implementation

| ID | Question | Proposed default for review | Affected requirements/tests |
| --- | --- | --- | --- |
| Q01 | Does event cancellation mean deletion or a retained cancelled status? What happens to associated bookings and the waiting list? | Delete event and associated bookings together; no notifications or history. Confirm this before defining acceptance behavior. | REQ-04, REQ-10; T04, T10, T13 |
| Q02 | May capacity be reduced below confirmed attendance? Is zero capacity valid? | Require positive capacity; reject reductions below confirmed count; do not demote participants. On increase, promote FIFO into free seats. | REQ-03, REQ-08–11; T03, T08, T09, T11 |
| Q03 | Are past events allowed? Is a time/timezone required? Can a booked event be moved into the past? | Parse a real calendar date with datetime.date.fromisoformat and require canonical YYYY-MM-DD. Provisionally allow past dates until assignment policy is confirmed. | REQ-01, REQ-03, REQ-15; T01, T03, T15 |
| Q04 | What should happen for missing, unreadable, corrupt, or unsupported storage, and for failed writes? Is retry/backup recovery required? | Missing file starts empty; other load failures stop safely with a message, preserving the file. Failed save keeps prior active state and disk snapshot; show error and allow retry. Confirm recovery workflow. | REQ-13–16; T13–16 |
| Q05 | Which participant fields define duplicates, and how much email validation is required? | Name/email fields; normalized email unique per event across both statuses. | REQ-06–07, REQ-15; T06–07, T15 |
| Q06 | What exact report fields and search filters are assessed? Are cancelled/history statistics required? | Current per-event counts and totals; title/location substring search, no history. | REQ-05, REQ-12; T05, T12 |

## Planned boundary and failure scenarios

In addition to requirements.md: capacity one with several waiting entries;
cancel a middle waiting entry then the confirmed participant; verify original
FIFO order; duplicate email with whitespace/case changes; same participant on
different events; invalid update leaves queues unchanged; round trip after
promotion; malformed JSON and valid JSON with broken references/duplicate queue
IDs; simulated permission/write failure; empty data and unknown IDs. Test Q01–Q06
outcomes after policy review, including capacity reduction and calendar edge
cases such as invalid days and leap years.
