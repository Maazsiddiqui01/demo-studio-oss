"""Validator rules (docs/storyboard-format.md). Run: .venv/Scripts/python -m pytest tests"""
from pathlib import Path

import pytest
import yaml

from demo_studio.storyboard import StoryboardError, load

BASE = {
    "version": 1, "name": "test-sb", "mode": "public", "title": "A title", "eyebrow": "E",
    "base_url": "http://localhost:5199", "voice": "af_heart", "sources": ["a source"],
    "banned_terms": ["Acme"],
    "steps": [{"id": "a", "action": "wait_for", "target": "#x", "caption": {"n": 1, "title": "One"},
               "narration": "Plain words."}],
}


def build(tmp_path: Path, **over) -> Path:
    d = yaml.safe_load(yaml.safe_dump(BASE))
    for k, v in over.items():
        if v is None:
            d.pop(k, None)
        else:
            d[k] = v
    p = tmp_path / "sb.yaml"
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    return p


def errors(p: Path) -> str:
    with pytest.raises(StoryboardError) as e:
        load(p)
    return "\n".join(e.value.errors)


def test_ok(tmp_path):
    assert load(build(tmp_path)).mode == "public"


def test_mode_required(tmp_path):
    assert "mode: required" in errors(build(tmp_path, mode=None))


def test_dash_rejected(tmp_path):
    steps = [dict(BASE["steps"][0], narration="One thing \u2014 another.")]
    assert "em dash" in errors(build(tmp_path, steps=steps))


def test_banned_term_and_contacts(tmp_path):
    steps = [dict(BASE["steps"][0], narration="Ask Acme at hello@example.com or +1 415 555 0100.")]
    e = errors(build(tmp_path, steps=steps))
    assert "banned" in e and "email" in e and "phone" in e


def test_public_no_auth(tmp_path):
    assert "auth must be null" in errors(build(tmp_path, auth="crm"))


def test_handover_rules(tmp_path):
    steps = [{"id": "a", "action": "click", "target": "button:has-text('Send')", "caption": {"n": 1, "title": "One"},
              "narration": "Click send."}]
    e = errors(build(tmp_path, mode="handover", client="c", delivery={"public": True}, steps=steps))
    assert "auth is required" in e and "delivery.public must be false" in e and "may write to the live system" in e


def test_live_write_needs_owner(tmp_path):
    steps = [dict(BASE["steps"][0], live_write=True)]
    assert "confirmed_by_owner" in errors(build(tmp_path, steps=steps))


def test_speed_up_label_added(tmp_path):
    steps = [dict(BASE["steps"][0], speed_up=True, caption={"n": 1, "title": "One", "sub": "Waiting"})]
    sb = load(build(tmp_path, steps=steps))
    assert sb.steps[0].caption.sub == "Waiting (sped up)"


def test_dates_are_not_phones(tmp_path):
    steps = [dict(BASE["steps"][0], narration="Live since 2025-08-01, refreshed at 08:00.")]
    load(build(tmp_path, steps=steps))


HANDOVER_WRITE = {
    "mode": "handover", "client": "acme-client", "banned_terms": [],
    "delivery": {"public": False, "local_only": True},
    "steps": [{"id": "t", "action": "type", "target": "input[name=x]", "text": "hello",
               "caption": {"n": 1, "title": "Type"}, "narration": "Plain words."}],
}


def test_local_copy_allows_writes_without_auth(tmp_path):
    sb = load(build(tmp_path, **HANDOVER_WRITE, local_copy=True, base_url="http://127.0.0.1:3217"))
    assert sb.local_copy and sb.auth is None


def test_local_copy_refuses_a_remote_url(tmp_path):
    e = errors(build(tmp_path, **HANDOVER_WRITE, local_copy=True, base_url="https://app.example.com"))
    assert "local_copy: base_url must be" in e
    assert "auth is required" in e and "may write to the live system" in e


def test_handover_write_still_needs_owner_yes_without_local_copy(tmp_path):
    e = errors(build(tmp_path, **HANDOVER_WRITE, auth="acme"))
    assert "may write to the live system" in e


def test_figures_on_separate_lines_are_not_a_phone():
    from demo_studio.textscan import find_contacts
    assert not find_contacts("51510\n36190\n30772\n30320", "screen")
    assert find_contacts("Call +1 415 555 0100 today", "screen")


def test_desktop_handover_key_and_position_clicks(tmp_path):
    steps = [{"id": "s", "action": "key", "keys": "^s", "caption": {"n": 1, "title": "Save"}, "narration": "Plain words."},
             {"id": "c", "action": "click", "target": "at=10,10", "caption": {"n": 2, "title": "Tab"}, "narration": "Plain words."}]
    over = dict(mode="handover", client="acme-client", banned_terms=[], base_url=None, driver="desktop",
                app={"window": "Report"}, delivery={"public": False, "local_only": True})
    assert "may save, delete or submit" in errors(build(tmp_path, steps=steps, **over))
    steps[0]["keys"] = "^{PGDN}"
    sb = load(build(tmp_path, steps=steps, **over))
    assert any("at=X,Y" in w for w in sb.warnings)
