"""Storage-boundary validation and replacement failure guarantees."""

from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch

import pytest

import storage


@pytest.fixture
def state():
    """One full event with two waiting students; every record is synthetic."""
    return {
        "schema_version": 1,
        "events": {
            "e1": {
                "event_id": "e1",
                "title": "Workshop",
                "date": "2024-02-29",
                "venue": "Room A",
                "capacity": 1,
                "status": "active",
                "waiting_list": ["b3", "b2"],
            }
        },
        "bookings": {
            key: {
                "booking_id": key,
                "event_id": "e1",
                "student_id": student,
                "student_name": "Sample Student",
                "status": status,
            }
            for key, student, status in [
                ("b1", "001", "confirmed"),
                ("b2", "002", "waiting"),
                ("b3", "003", "waiting"),
            ]
        },
    }


def write_raw(tmp_path, state):
    path = tmp_path / "eventhub.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    return path


def test_missing_file_returns_fresh_empty_state(tmp_path):
    directory = tmp_path / "not-created"
    first = storage.load_state(directory)
    assert first == {"schema_version": 1, "events": {}, "bookings": {}}
    first["events"]["changed"] = {}
    assert storage.load_state(directory) == storage.empty_state()
    assert not directory.exists()


def test_round_trip_and_fifo_without_mutation(tmp_path, state):
    original = deepcopy(state)
    storage.save_state(state, tmp_path)
    loaded = storage.load_state(tmp_path)
    assert loaded == original == state
    assert loaded["events"]["e1"]["waiting_list"] == ["b3", "b2"]
    loaded["events"]["e1"]["waiting_list"].clear()
    assert storage.load_state(tmp_path) == original
    assert list(tmp_path.iterdir()) == [tmp_path / "eventhub.json"]


def test_load_existing_json(tmp_path, state):
    write_raw(tmp_path, state)
    assert storage.load_state(tmp_path) == state


@pytest.mark.parametrize("raw", [b'{"schema_version":', b"\xff", b"null", b"[]"])
def test_damaged_data_is_preserved(tmp_path, raw):
    path = tmp_path / "eventhub.json"
    path.write_bytes(raw)
    with pytest.raises(ValueError):
        storage.load_state(tmp_path)
    assert path.read_bytes() == raw


@pytest.mark.parametrize("version", [0, 2, True, 1.0, "1", None])
def test_unsupported_schema(tmp_path, state, version):
    state["schema_version"] = version
    write_raw(tmp_path, state)
    with pytest.raises(ValueError, match="schema_version"):
        storage.load_state(tmp_path)


@pytest.mark.parametrize("field", ["schema_version", "events", "bookings"])
def test_missing_root_keys(state, field):
    del state[field]
    with pytest.raises(ValueError):
        storage.validate_state(state)


@pytest.mark.parametrize("container", ["events", "bookings"])
@pytest.mark.parametrize("value", [[], None, "wrong", 1])
def test_invalid_containers(state, container, value):
    state[container] = value
    with pytest.raises(ValueError):
        storage.validate_state(state)


@pytest.mark.parametrize("record", ["root", "event", "booking"])
def test_unexpected_fields(state, record):
    target = {
        "root": state,
        "event": state["events"]["e1"],
        "booking": state["bookings"]["b1"],
    }[record]
    target["unexpected"] = 1
    with pytest.raises(ValueError):
        storage.validate_state(state)


@pytest.mark.parametrize(
    "kind,fields",
    [
        (
            "events",
            [
                "event_id",
                "title",
                "date",
                "venue",
                "capacity",
                "status",
                "waiting_list",
            ],
        ),
        (
            "bookings",
            ["booking_id", "event_id", "student_id", "student_name", "status"],
        ),
    ],
)
def test_every_record_field_is_required(state, kind, fields):
    key = "e1" if kind == "events" else "b1"
    for field in fields:
        invalid = deepcopy(state)
        del invalid[kind][key][field]
        with pytest.raises(ValueError):
            storage.validate_state(invalid)


@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, "1", None])
def test_invalid_capacity(state, value):
    state["events"]["e1"]["capacity"] = value
    with pytest.raises(ValueError, match="capacity"):
        storage.validate_state(state)


@pytest.mark.parametrize(
    "value",
    [
        "2024-2-29",
        "20240229",
        "2023-02-29",
        "2024-13-01",
        "0000-01-01",
        "2024-02-29T00:00:00",
        " 2024-02-29",
        "2024-02-29\n",
        None,
        20240229,
    ],
)
def test_invalid_dates(state, value):
    state["events"]["e1"]["date"] = value
    with pytest.raises(ValueError, match="date"):
        storage.validate_state(state)


@pytest.mark.parametrize("kind,key", [("events", "e1"), ("bookings", "b1")])
@pytest.mark.parametrize("status", ["unknown", None, [], {}])
def test_invalid_status(state, kind, key, status):
    state[kind][key]["status"] = status
    with pytest.raises(ValueError):
        storage.validate_state(state)


@pytest.mark.parametrize(
    "kind,key,field",
    [
        ("events", "e1", "event_id"),
        ("bookings", "b1", "booking_id"),
    ],
)
def test_mismatched_ids(state, kind, key, field):
    state[kind][key][field] = "other"
    with pytest.raises(ValueError, match="mismatched"):
        storage.validate_state(state)


@pytest.mark.parametrize(
    "kind,key,field",
    [
        ("events", "e1", "title"),
        ("events", "e1", "venue"),
        ("bookings", "b1", "student_id"),
        ("bookings", "b1", "student_name"),
    ],
)
@pytest.mark.parametrize("value", ["", " ", " padded ", 1, None])
def test_invalid_text_fields(state, kind, key, field, value):
    state[kind][key][field] = value
    with pytest.raises(ValueError):
        storage.validate_state(state)


@pytest.mark.parametrize("value", ["missing", [], None, ""])
def test_unknown_or_invalid_event_reference(state, value):
    state["bookings"]["b1"]["event_id"] = value
    with pytest.raises(ValueError):
        storage.validate_state(state)


def test_duplicate_identity_across_statuses(state):
    state["bookings"]["b2"]["student_id"] = "001"
    with pytest.raises(ValueError, match="Duplicate student"):
        storage.validate_state(state)


def test_identity_is_case_sensitive_and_scoped_to_event(state):
    state["bookings"]["b1"]["student_id"] = "AbC"
    state["bookings"]["b2"]["student_id"] = "abc"
    state["events"]["e2"] = {
        **deepcopy(state["events"]["e1"]),
        "event_id": "e2",
        "waiting_list": [],
    }
    state["bookings"]["b4"] = {
        **state["bookings"]["b1"],
        "booking_id": "b4",
        "event_id": "e2",
    }
    storage.validate_state(state)


def test_over_capacity(state):
    state["bookings"]["b2"]["status"] = "confirmed"
    state["events"]["e1"]["waiting_list"] = ["b3"]
    with pytest.raises(ValueError, match="exceeds capacity"):
        storage.validate_state(state)


@pytest.mark.parametrize(
    "queue",
    [None, {}, "b2", [1], ["missing"], ["b2", "b2", "b3"], ["b1", "b2", "b3"], ["b2"]],
)
def test_invalid_waiting_lists(state, queue):
    state["events"]["e1"]["waiting_list"] = queue
    with pytest.raises(ValueError):
        storage.validate_state(state)


def test_queue_cannot_reference_another_event(state):
    state["events"]["e2"] = {
        **deepcopy(state["events"]["e1"]),
        "event_id": "e2",
    }
    with pytest.raises(ValueError, match="queue"):
        storage.validate_state(state)


def test_waiting_with_vacant_seat_rejected(state):
    state["events"]["e1"]["capacity"] = 2
    with pytest.raises(ValueError, match="available seats"):
        storage.validate_state(state)


@pytest.mark.parametrize("with_bookings", [True, False])
def test_invalid_cancelled_event(state, with_bookings):
    state["events"]["e1"]["status"] = "cancelled"
    if not with_bookings:
        state["bookings"].clear()
    with pytest.raises(ValueError):
        storage.validate_state(state)


def test_valid_cancelled_event(state):
    state["events"]["e1"]["status"] = "cancelled"
    state["events"]["e1"]["waiting_list"].clear()
    state["bookings"].clear()
    storage.validate_state(state)


@pytest.mark.parametrize(
    "raw",
    [
        '{"schema_version": 1, "schema_version": 1, "events": {}, "bookings": {}}',
        '{"schema_version": 1, "events": {"e": {}, "e": {}}, "bookings": {}}',
        '{"schema_version": 1, "events": {"e": {"title": "a", "title": "b"}}, "bookings": {}}',
    ],
)
def test_duplicate_json_keys_at_all_levels(tmp_path, raw):
    path = tmp_path / "eventhub.json"
    path.write_text(raw)
    with pytest.raises(ValueError, match="Duplicate JSON"):
        storage.load_state(tmp_path)
    assert path.read_text() == raw


def test_missing_authority_with_leftover_temporary_requires_review(tmp_path):
    artifact = tmp_path / "eventhub-abandoned.tmp"
    artifact.write_text("unsaved")
    with pytest.raises(ValueError, match="review"):
        storage.load_state(tmp_path)
    assert artifact.read_text() == "unsaved"


def test_valid_authority_ignores_leftover_temporary(tmp_path, state):
    write_raw(tmp_path, state)
    (tmp_path / "eventhub-abandoned.tmp").write_text("bad")
    assert storage.load_state(tmp_path) == state


def test_unreadable_file_propagates_oserror(tmp_path):
    with patch.object(Path, "open", side_effect=PermissionError("denied")):
        with pytest.raises(OSError, match="denied"):
            storage.load_state(tmp_path)


def test_candidate_failure_preserves_existing_file(tmp_path, state):
    path = write_raw(tmp_path, state)
    before = path.read_bytes()
    state["events"]["e1"]["capacity"] = False
    with pytest.raises(ValueError):
        storage.save_state(state, tmp_path)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("phase", ["create", "write", "readback", "replace"])
@pytest.mark.parametrize("existing", [True, False])
def test_precommit_failures_preserve_authority(tmp_path, state, phase, existing):
    path = tmp_path / "eventhub.json"
    if existing:
        write_raw(tmp_path, storage.empty_state())
    before = path.read_bytes() if existing else None
    targets = {
        "create": "storage.tempfile.NamedTemporaryFile",
        "write": "storage.json.dump",
        "readback": "storage._read_snapshot",
        "replace": "storage.os.replace",
    }
    candidate = deepcopy(state)
    with patch(targets[phase], side_effect=OSError(f"{phase} failed")):
        with pytest.raises(OSError, match=f"{phase} failed"):
            storage.save_state(candidate, tmp_path)
    assert candidate == state
    assert path.read_bytes() == before if existing else not path.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_readback_must_match_candidate(tmp_path, state):
    path = write_raw(tmp_path, storage.empty_state())
    before = path.read_bytes()
    with patch("storage._read_snapshot", return_value=storage.empty_state()):
        with pytest.raises(ValueError, match="does not match"):
            storage.save_state(state, tmp_path)
    assert path.read_bytes() == before


def test_serialization_typeerror_is_controlled(tmp_path, state):
    with patch("storage.json.dump", side_effect=TypeError("cannot serialize")):
        with pytest.raises(ValueError, match="Cannot serialize"):
            storage.save_state(state, tmp_path)
    assert not (tmp_path / "eventhub.json").exists()


def test_cleanup_failure_does_not_mask_precommit_error(tmp_path, state, caplog):
    path = write_raw(tmp_path, storage.empty_state())
    before = path.read_bytes()
    with patch("storage.os.replace", side_effect=OSError("replace failed")):
        with patch.object(Path, "unlink", side_effect=OSError("cleanup failed")):
            with pytest.raises(OSError, match="replace failed"):
                storage.save_state(state, tmp_path)
    assert path.read_bytes() == before
    assert "cleanup failed" in caplog.text


def test_postcommit_cleanup_failure_only_warns(tmp_path, state, caplog):
    with patch.object(Path, "unlink", side_effect=OSError("cleanup failed")):
        assert storage.save_state(state, tmp_path) is None
    assert storage.load_state(tmp_path) == state
    assert "cleanup failed" in caplog.text


def test_replace_receives_validated_sibling(tmp_path, state):
    real_replace = storage.os.replace
    seen = []

    def inspect_replace(source, destination):
        assert source.parent == destination.parent == tmp_path
        assert source.suffix == ".tmp"
        assert storage._read_snapshot(source) == state
        seen.append(destination)
        real_replace(source, destination)

    with patch("storage.os.replace", side_effect=inspect_replace):
        storage.save_state(state, tmp_path)
    assert seen == [tmp_path / "eventhub.json"]
    assert storage.load_state(tmp_path) == state


@pytest.mark.parametrize("kind,key", [("events", "e1"), ("bookings", "b1")])
@pytest.mark.parametrize("value", [None, [], "record"])
def test_record_must_be_dictionary(state, kind, key, value):
    state[kind][key] = value
    with pytest.raises(ValueError):
        storage.validate_state(state)


@pytest.mark.parametrize("phase", ["flush", "close"])
def test_temporary_flush_or_close_failure_preserves_file(tmp_path, state, phase):
    from contextlib import contextmanager
    from types import SimpleNamespace

    path = write_raw(tmp_path, storage.empty_state())
    before = path.read_bytes()
    real_temporary = storage.tempfile.NamedTemporaryFile

    def fail_flush():
        raise OSError("flush failed")

    @contextmanager
    def failing_temporary(**kwargs):
        with real_temporary(**kwargs) as stream:
            yield SimpleNamespace(
                name=stream.name,
                write=stream.write,
                flush=fail_flush if phase == "flush" else stream.flush,
            )
        if phase == "close":
            raise OSError("close failed")

    with patch("storage.tempfile.NamedTemporaryFile", failing_temporary):
        with pytest.raises(OSError, match=f"{phase} failed"):
            storage.save_state(state, tmp_path)
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("committed", [False, True])
def test_interruption_before_or_after_commit_loads_correct_state(
    tmp_path, state, committed
):
    old = storage.empty_state()
    write_raw(tmp_path, old)
    real_replace = storage.os.replace

    def interrupt(source, destination):
        if committed:
            real_replace(source, destination)
        raise SystemExit("simulated interruption")

    with patch("storage.os.replace", side_effect=interrupt):
        with pytest.raises(SystemExit, match="interruption"):
            storage.save_state(state, tmp_path)
    assert storage.load_state(tmp_path) == (state if committed else old)


def test_partial_temporary_write_preserves_authority(tmp_path, state):
    path = write_raw(tmp_path, storage.empty_state())
    before = path.read_bytes()

    def partial_write(candidate, stream, **kwargs):
        stream.write('{"schema_version":')
        raise OSError("disk full")

    with patch("storage.json.dump", side_effect=partial_write):
        with pytest.raises(OSError, match="disk full"):
            storage.save_state(state, tmp_path)
    assert path.read_bytes() == before


def test_deeply_nested_json_is_controlled_and_preserved(tmp_path):
    path = tmp_path / "eventhub.json"
    raw = ("[" * 10000 + "0" + "]" * 10000).encode("utf-8")
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="JSON nesting is too deep") as caught:
        storage.load_state(tmp_path)
    assert str(path) in str(caught.value)
    assert isinstance(caught.value.__cause__, RecursionError)
    assert path.read_bytes() == raw


def test_unrelated_validation_recursion_is_not_translated(tmp_path, state):
    write_raw(tmp_path, state)
    with patch("storage.validate_state", side_effect=RecursionError("validation bug")):
        with pytest.raises(RecursionError, match="validation bug"):
            storage.load_state(tmp_path)


@pytest.mark.parametrize(
    "corruption", ["{", '{"schema_version": 2, "events": {}, "bookings": {}}']
)
def test_corrupted_temporary_snapshot_preserves_authority(tmp_path, state, corruption):
    from contextlib import contextmanager

    path = write_raw(tmp_path, storage.empty_state())
    before = path.read_bytes()
    original_candidate = deepcopy(state)
    real_temporary = storage.tempfile.NamedTemporaryFile
    temporary_paths = []

    @contextmanager
    def corrupt_after_close(**kwargs):
        with real_temporary(**kwargs) as stream:
            temporary_path = Path(stream.name)
            temporary_paths.append(temporary_path)
            yield stream
        # The real write/flush/close finished; corrupt actual bytes before readback.
        assert json.loads(temporary_path.read_text(encoding="utf-8")) == state
        temporary_path.write_text(corruption, encoding="utf-8")

    with patch("storage.tempfile.NamedTemporaryFile", corrupt_after_close):
        with patch("storage.os.replace") as replace:
            with pytest.raises(ValueError):
                storage.save_state(state, tmp_path)
            replace.assert_not_called()
    assert path.read_bytes() == before
    assert storage.load_state(tmp_path) == storage.empty_state()
    assert state == original_candidate
    assert len(temporary_paths) == 1
    assert not temporary_paths[0].exists()
    assert not list(tmp_path.glob("eventhub-*.tmp"))
