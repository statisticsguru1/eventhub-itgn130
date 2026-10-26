"""Verify that the scaffold modules are available from this repository."""

import importlib
from pathlib import Path

import pytest


@pytest.mark.parametrize("module_name", ["main", "events", "bookings", "storage"])
def test_project_module_is_importable(module_name):
    """Import each module and guard against importing a namesake package."""
    module = importlib.import_module(module_name)
    expected_path = Path(__file__).resolve().parents[1] / f"{module_name}.py"

    assert Path(module.__file__).resolve() == expected_path
