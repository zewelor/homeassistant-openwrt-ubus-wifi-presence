"""Tests for the hassfest wrapper lifecycle."""

from pathlib import Path

HASSFEST_SCRIPT = Path(__file__).parents[1] / "hassfest"


def test_hassfest_activates_virtual_environment_before_version_detection() -> None:
    """Ensure direct invocation resolves Home Assistant from the project venv."""
    script = HASSFEST_SCRIPT.read_text(encoding="utf-8")

    assert script.index("\nactivate_venv\n") < script.index("# Detect Home Assistant version to use")
