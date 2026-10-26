# Proposed data model

These fields and representations are design proposals, not additional assignment
requirements. JSON persistence and FIFO behavior are mandatory (REQ-09, REQ-13).

## State

A root dictionary contains `schema_version: 1`, `events` keyed by event ID, and
`bookings` keyed by booking ID. Generate string IDs with standard-library
`uuid.uuid4`; persist them unchanged. No separate participant registry is needed
initially: participant name/email belong to each booking. A person can register
for multiple events.

Each event contains `event_id`, `title`, `date` (proposed `YYYY-MM-DD`), `location`,
`capacity` (positive integer), and `waiting_list` (ordered list of booking IDs).
Each booking contains `booking_id`, `event_id`, `participant_name`,
`participant_email` (normalized identity), and `status` (`confirmed` or `waiting`).
Proposed cancellation removes the booking rather than retaining history; reports
therefore describe current registrations only. Historical reports need a further
decision if the assignment expects them.

## Illustrative JSON shape

This is an example, not a runtime data file or a final submission artifact.

```json
{
  "schema_version": 1,
  "events": {
    "event-a": {
      "event_id": "event-a",
      "title": "Python Workshop",
      "date": "2026-11-20",
      "location": "Room 101",
      "capacity": 1,
      "waiting_list": ["booking-b"]
    }
  },
  "bookings": {
    "booking-a": {
      "booking_id": "booking-a",
      "event_id": "event-a",
      "participant_name": "Alex",
      "participant_email": "alex@example.com",
      "status": "confirmed"
    },
    "booking-b": {
      "booking_id": "booking-b",
      "event_id": "event-a",
      "participant_name": "Sam",
      "participant_email": "sam@example.com",
      "status": "waiting"
    }
  }
}
```

## Invariants and derived values

- Dictionary keys equal embedded IDs; all booking event references exist.
- Capacity is a positive integer; explicitly reject booleans as capacities.
- Confirmed count never exceeds capacity.
- An event/email pair occurs at most once across both booking statuses.
- Every waiting booking appears exactly once in its event's waiting list;
  confirmed bookings never appear there. Queue order survives save/load.
- Derive confirmed counts and available seats from bookings; do not persist
  redundant counters. The event's queue list is the authoritative FIFO order.
- Validate types, required fields, supported schema version, references, and
  invariants on loading before accepting any state. Do not silently discard
  malformed records. Error recovery policy remains Q04.

Proposed report structure: `{"events": [per_event_metrics], "totals": {...}}`.
Each event metric has ID/title, capacity, confirmed, waiting, and available seats;
totals aggregate events, confirmed bookings, and waiting bookings. Counts refer
to bookings, not distinct people across events.
