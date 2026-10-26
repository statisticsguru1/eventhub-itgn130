# EventHub data model

## Authority and implementation status

The assignment mandates event ID, title, date, venue, capacity, status; student ID
and name; capacity/FIFO behavior; and JSON persistence. The dictionary layout and
policies below are approved project decisions, not a prescribed assignment schema.
These structures are documentation only. No application behavior is implemented.
The single-file persistence contract in business_rules.md is approved in
Milestone 2.3. The in-memory state and persisted snapshot use the same structure.

## In-memory state

Use plain dictionaries/lists, functions, and Python 3.10+. No classes or separate
student registry are needed. State has schema_version: 1, events keyed by event ID,
and bookings keyed by booking ID. Generate unique string IDs with uuid.uuid4;
check for collisions before inserting. IDs persist unchanged.

| Record | Fields |
| --- | --- |
| Event | event_id: unique string; title: nonempty string; date: canonical YYYY-MM-DD; venue: nonempty string; capacity: positive integer; status: active or cancelled; waiting_list: ordered list of booking IDs |
| Registration | booking_id: unique string; event_id: event reference; student_id: nonempty trimmed string; student_name: nonempty string; status: confirmed or waiting |

Student IDs are case-sensitive after trimming; retain leading zeros and impose no
invented length restriction. Student names are display attributes, not unique
keys. Trim title, venue, and student_name and reject empty results. A student may
register for different events and again after registration cancellation.

## Illustrative state (synthetic only)

```json
{
  "schema_version": 1,
  "events": {
    "event-a": {
      "event_id": "event-a",
      "title": "Python Workshop",
      "date": "2026-11-20",
      "venue": "Room 101",
      "capacity": 1,
      "status": "active",
      "waiting_list": ["booking-b"]
    }
  },
  "bookings": {
    "booking-a": {
      "booking_id": "booking-a",
      "event_id": "event-a",
      "student_id": "001",
      "student_name": "Sample Student A",
      "status": "confirmed"
    },
    "booking-b": {
      "booking_id": "booking-b",
      "event_id": "event-a",
      "student_id": "002",
      "student_name": "Sample Student B",
      "status": "waiting"
    }
  }
}
```

## Invariants

- Dictionary keys equal embedded IDs; all IDs are nonempty strings.
- Every booking references an existing active event. Cancelled events are retained
  but have no bookings and an empty waiting_list.
- Capacity is an integer greater than zero; reject bool explicitly. Confirmed
  count never exceeds capacity. schema_version must also be an exact integer.
- An (event_id, trimmed case-sensitive student_id) occurs once across both statuses.
- Status values are restricted to their documented enumerations.
- Every waiting booking occurs exactly once in its own event queue. No confirmed
  booking occurs in a queue; queue entries cannot reference another event.
- After a successful operation, an active event cannot have waiting students and
  unfilled seats simultaneously. Queue order is authoritative FIFO order.
- Validate exact date format and a real calendar date; past dates are permitted.
- On load, reject malformed types, missing fields, duplicate JSON object keys,
  unsupported schema versions, broken references, and violated invariants. Do not
  silently repair or discard records. Reject unexpected record fields for schema 1.
- Returned read records must not expose nested mutable lists from active state.

## Derived views

Search rows include event_id, title, date, venue, capacity, status, confirmed_count,
and waiting_count; sort by (date, event_id). Counts are derived from bookings and
must agree with queue membership.

Report shape: totals with retained_events, active_events, cancelled_events,
confirmed_registrations, waiting_registrations, available_seats; plus leaders, a
list of event_id/title/confirmed_count rows ordered by (date, event_id). Leaders
are active events tied at the largest positive confirmed count; otherwise leaders
is empty and main displays “No confirmed registrations”. Available seats sum
capacity minus confirmed count for active events only. Cancelled events contribute
zero seats and registrations. No derived counters are persisted.

## Approved persistence representation

The sole authoritative snapshot is data/eventhub.json, resolved relative to the
application root rather than the caller's working directory. Its root has exactly
schema_version (integer 1), events (dictionary), and bookings (dictionary), as in
the illustrative state above. Each event stores its ordered waiting_list of booking
IDs. No separate persisted counters or storage metadata are required.

Use a unique temporary sibling ending in .tmp and os.replace as the logical commit
point. Validate the candidate and the serialized readback before replacement;
adopt candidate only after replacement succeeds. See business_rules.md for precise
failure, startup, cleanup, and crash behavior. Corrupt or incompatible snapshots
are preserved and never silently replaced with empty data.

The existing ignore rules cover runtime data/*.json and data/*.tmp. Future original
nonsensitive sample eventhub.json must be included explicitly in a tracked sample
location, with instructions for copying it into the runtime directory. No sample
files are created in this milestone. The assignment's two sample filenames are
starter guidance; the approved design stores all state in one authoritative file.
