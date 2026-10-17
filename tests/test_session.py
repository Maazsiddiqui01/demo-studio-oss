"""Session write-back keeps cookies and auth entries only (studio/session.py)."""
import json

from demo_studio import session


def fake_state(big: int = 0) -> dict:
    return {
        "cookies": [{"name": "sid", "value": "c", "domain": "app.example", "path": "/"}],
        "origins": [
            {"origin": "https://app.example", "localStorage": [
                {"name": "sb-abcd1234-auth-token", "value": "{\"access_token\":\"x\"}"},
                {"name": "hz-columns:companies", "value": "x" * big},
                {"name": "theme", "value": "dark"},
                {"name": "msal.token.keys.client", "value": "k"},
            ], "indexedDB": [{"name": "firebaseLocalStorageDb", "version": 1, "stores": []},
                             {"name": "app-cache", "version": 1, "stores": []}]},
            {"origin": "https://cdn.example", "localStorage": [{"name": "prefs", "value": "y"}]},
        ],
    }


def test_slim_keeps_cookies_and_auth_entries_only():
    small, dropped = session.slim(fake_state(big=10))
    assert small["cookies"] == fake_state()["cookies"]
    assert len(small["origins"]) == 1
    names = [i["name"] for i in small["origins"][0]["localStorage"]]
    assert names == ["sb-abcd1234-auth-token", "msal.token.keys.client"]
    assert [d["name"] for d in small["origins"][0]["indexedDB"]] == ["firebaseLocalStorageDb"]
    assert len(dropped) == 4  # hz-columns, theme, app-cache, cdn prefs


def test_write_back_drops_a_huge_preference_store(tmp_path):
    dest = tmp_path / "s.json"
    assert session.write_back(fake_state(big=5_000_000), dest, log=lambda *_: None)
    data = json.loads(dest.read_text(encoding="utf-8"))
    assert dest.stat().st_size < 2000
    assert all(i["name"] != "hz-columns:companies" for o in data["origins"] for i in o["localStorage"])


def test_write_back_refuses_above_the_cap_and_keeps_the_old_file(tmp_path):
    dest = tmp_path / "s.json"
    dest.write_text("old", encoding="utf-8")
    st = fake_state()
    st["origins"][0]["localStorage"][0]["value"] = "t" * (session.MAX_BYTES + 10)
    msgs = []
    assert not session.write_back(st, dest, log=msgs.append)
    assert dest.read_text(encoding="utf-8") == "old"
    assert "not saved" in msgs[0]
