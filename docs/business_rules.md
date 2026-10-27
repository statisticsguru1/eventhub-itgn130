# Implemented business rules

The official assignment mandates the core workflows; the precise identity, date,
status, reporting and save policies below are approved project decisions embodied
in the final implementation. The application is complete through Milestone 3.6.

## Events and validation

- Each new event receives a generated unique UUID string; a generation collision
  is rejected before insertion. IDs are nonempty strings and lookups are exact.
- Title and venue must be nonempty after surrounding whitespace is trimmed.
- Date must be a real canonical `YYYY-MM-DD` date. Past dates are allowed.
- Capacity is a positive integer; booleans are rejected by domain/state validation.
- Events start active. Only title, date, venue and capacity may be edited.
- Cancelled events remain visible, cannot be edited, cannot accept registrations,
  and cannot be reactivated. Repeated cancellation is an explanatory no-op.
- Capacity cannot be reduced below confirmed attendance; no participant is demoted.
  Capacity increase promotes as many FIFO waiters as the seats permit before save.

## Participant identity and registration

- Student ID and name are required nonempty strings with surrounding whitespace
  trimmed. IDs remain textual, preserving leading zeros and case.
- Uniqueness is the normalized student ID within an event, across confirmed and
  waiting statuses. `001` differs from `1`; `ABC` differs from `abc`.
- A student may register for different events. Names do not establish identity.
- Registration requires an existing active event. It confirms if capacity remains;
  otherwise it appends an internal booking ID to the event's FIFO queue.
- Existing waiters cannot be bypassed by a newcomer during an unfinished capacity
  change. Complete promotion first. Booking IDs are generated uniquely and are
  internal, not user-facing console inputs or output.

## Cancellation and FIFO promotion

- Cancelling a registration removes its current record; no cancelled status,
  timestamp, queue position or history is persisted. Re-registration is allowed.
- Cancelling a waiting registration removes exactly its queue entry without
  promoting anyone and preserves the order of remaining waiters.
- Cancelling a confirmed registration promotes exactly the first waiter if any.
- Queue-consuming mutations preflight references, statuses, duplicates and complete
  waiting membership before mutation. Expected validation failures are atomic.
- Increasing capacity uses `fill_available_seats` to promote the fitting FIFO prefix.
- Event cancellation first changes status, then removes every associated booking
  and clears its queue without promotion. Cleanup accepts cancelled events only
  and returns sorted removed IDs internally. Other events/bookings are preserved.

## Search and display

- List/search include active and cancelled events, ordered by date then event ID.
- Keyword search trims the query and performs case-insensitive substring matching
  on title or venue; blank means all events.
- Date search validates a canonical real calendar date and matches it exactly.
- Views show ID, title, date, venue, capacity, status and confirmed/waiting counts.
  They omit the raw queue and internal booking IDs. No matches prints
  `No events found.` in the console.

## Reporting

- All retained events contribute to total events and the active/cancelled breakdown.
- Only active events contribute confirmed/waiting registration totals, available
  seats and most-registered leaders. Count registrations, not unique students.
- Available seats sum capacity minus confirmed count; do not subtract waiting count
  or include cancelled capacity.
- Most registered means highest positive confirmed count among active events.
  Return all ties in date/event-ID order; return none if the maximum is zero.
- Reports are composed in `main.summary_report`; counts and report values are
  derived, independent data and never inserted into persisted event records.

## Application and console boundaries

- Each mutation deep-copies caller state, completes domain changes and result
  lookups, saves, and returns the candidate. The menu adopts it immediately before
  success output. Failure before return leaves the previous active binding intact.
- Empty and normalized-equal active edits still pass through domain validation;
  genuine no-ops and repeated event cancellation skip saving.
- The repeating menu exposes all workflows; optional edit inputs use exactly empty
  input to keep a value. Capacity text is converted to an integer at the UI boundary.
- Expected ValueError/KeyError/OSError errors get controlled messages. Ordinary
  useful validation messages remain intact; the known internal booking-ID collision
  alone maps to a friendly allocation message. Unexpected errors propagate.
- Startup is side-effect free on import. EOF/KeyboardInterrupt ends interaction
  cleanly. Reads and Exit do not save.

## Persistence safety

- The sole authority is `data/eventhub.json`, containing schema version, events and
  bookings. Both domain collections commit together.
- `save_state` validates the complete state, writes/closes a sibling temporary
  snapshot, reads it back, validates and compares it, then replaces authority.
- A pre-replacement failure leaves previous authoritative bytes unchanged. Once
  replacement succeeds, optional cleanup warnings do not negate that success.
- A genuine first run loads empty state without writing. Malformed, schema-invalid,
  duplicate-key or otherwise unsafe data is rejected without silent repair.
- Missing authority with abandoned temporary snapshots stops for review; startup
  does not delete them. A valid authority can be loaded despite stale temp files.
- One local writer is supported. No promise of concurrent-writer coordination or
  universal power-loss durability is made; a crash may commit without acknowledgement.

## Existing evidence

`tests/test_events.py` covers event validation, edits, searches and independent
snapshots. `tests/test_bookings.py` covers identity, capacity, FIFO, cleanup and
malformed-queue atomicity. `tests/test_storage.py` covers complete-state invariants
and save/load failure boundaries. `tests/test_main.py` covers completed operations,
no-ops, results, report arithmetic and views. `tests/test_menu.py` covers startup,
expected errors, state adoption, internal-ID sanitization and the persisted
normal/full/waiting/cancellation/promotion demonstration. `tests/test_imports.py`
covers module imports. Live presentation and screenshot evidence remain separate.
