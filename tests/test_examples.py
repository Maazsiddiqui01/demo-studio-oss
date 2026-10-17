from pathlib import Path

import pytest

from demo_studio.storyboard import load

EXAMPLES = sorted((Path(__file__).resolve().parent.parent / "examples").glob("*/*.yaml"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_example_storyboards_validate(path):
    sb = load(path)
    assert sb.steps
    for name in (sb.raw.get("variants") or {}):
        assert load(path, variant=name).steps
