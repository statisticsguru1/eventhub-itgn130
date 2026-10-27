# Implemented data model

The runtime authority is `data/eventhub.json`, a single UTF-8 JSON snapshot.
`samples/eventhub.json` has the same schema but is never automatically loaded.
There are no separate authoritative event/booking files, persisted counters,
participant registry, audit history, or cancelled-booking records.

## Exact root structure

```json
{
  "schema_version": 1,
  "events": {},
  "bookings": {}
}
```

All three keys are required and extra keys are rejected. `schema_version` must be
integer 1 (not boolean); events and bookings are dictionaries keyed by their IDs.
Duplicate JSON object keys are rejected at every object level.

## Event record — exactly seven fields

| Field | Type / contract |
| --- | --- |
| `event_id` | Nonempty string equal to its event dictionary key |
| `title` | Trimmed nonempty string |
| `date` | Canonical ASCII `YYYY-MM-DD`, real calendar date; past dates permitted |
| `venue` | Trimmed nonempty string |
| `capacity` | Positive integer, excluding boolean |
| `status` | `active` or `cancelled` |
| `waiting_list` | Ordered list of unique nonempty booking-ID strings; sole persisted FIFO representation |

Application creation generates IDs with `str(uuid.uuid4())` and rejects collisions.
Validation requires nonempty matching IDs, not UUID syntax. Event IDs are looked
up exactly. Cancelled events are retained and cannot be edited/reactivated.

## Booking record — exactly five fields

| Field | Type / contract |
| --- | --- |
| `booking_id` | Nonempty string equal to its booking dictionary key; generated UUID string on registration |
| `event_id` | Existing active event ID |
| `student_id` | Trimmed nonempty string, preserving case and leading zeros |
| `student_name` | Trimmed nonempty string |
| `status` | `confirmed` or `waiting` |

Student identity is unique per `(event_id, student_id)` across both statuses,
not globally unique. No integer conversion or case folding is applied. Cancellation
removes the booking record; re-registration creates a new booking.

## Completed-state invariants

- Every booking references an existing active event.
- Every waiting booking appears exactly once in its own event's queue.
- Every queue entry references a waiting booking of that event; confirmed bookings
  never appear in a queue. Dictionary insertion order is not FIFO order.
- Confirmed count never exceeds capacity. An active event cannot retain waiters
  while seats are available.
- A cancelled event has no bookings and an empty waiting list.
- Capacity increase and event cancellation intermediates are completed by main
  orchestration before saving; storage rejects incomplete snapshots.

`storage.validate_state()` checks these relationships without changing state.
Counts are computed from bookings, never stored in event records.

## Derived list/search record — exactly eight fields

```text
event_id: str
title: str
date: str
venue: str
capacity: int
status: str
confirmed_count: int
waiting_count: int
```

`main.list_events_view`, `search_events_by_keyword_view`, and
`search_events_by_date_view` return fresh dictionaries in date/event-ID order.
The raw `waiting_list` and booking IDs are omitted. Cancelled events remain visible
with naturally zero counts in completed valid state.

## Derived summary report — exact keys

```text
{
    "total_events": int,
    "active_events": int,
    "cancelled_events": int,
    "confirmed_registrations": int,
    "waiting_registrations": int,
    "available_seats": int,
    "most_registered_events": [
        {"event_id": str, "title": str, "confirmed_count": int}
    ]
}
```

`main.summary_report()` counts all retained events for `total_events` and the
corresponding statuses for the breakdown. Only active events contribute confirmed
and waiting registration totals, available seats, and leaders. Registrations are
counted, not unique people. Available seats sum `capacity - confirmed_count`;
waiting registrations are not subtracted. Leaders include all events tied at the
positive maximum confirmed count, ordered by date then event ID. No positive
confirmed count means an empty leader list. No events means all numeric values
zero and an empty leader list. All derived values are read-only and never persisted.

## Sample snapshot

The fictional sample uses three UUID-style event IDs and four booking IDs:
a capacity-three active workshop with one confirmed booking; a full capacity-one
active workshop with one confirmed booking and two ordered waiters; and a retained
cancelled event with no bookings. Its report is total 3, active 2, cancelled 1,
confirmed 2, waiting 2, available seats 2, with both active events tied at one.

## Persistence and safety

A successful mutation saves the entire completed snapshot using a validated sibling
temporary file and `os.replace`. Startup loads only the authoritative filename.
Genuine first run may return empty state without writing. Invalid data is rejected,
not repaired or replaced. Missing authority plus abandoned temporary snapshots
requires review. See [architecture.md](architecture.md) for commit semantics and
single-writer/power-loss limitations.
