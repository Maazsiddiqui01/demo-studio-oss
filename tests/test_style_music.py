"""The framed look's layout, style and zoom validation, the music bed, folder publishing and the
ffmpeg-only probe."""
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from demo_studio import music, publish, style, tools
from demo_studio.storyboard import Style, StoryboardError, load

from test_validate import BASE, build


def test_layout_places_the_recording_1to1_with_fill_false():
    lay = style.layout(Style(frame=True, fill=False), (1440, 900))
    assert (lay["w"], lay["h"], lay["scale"]) == (1440, 900, 1.0)
    assert (lay["x"], lay["y"]) == (240, 90)  # centred on 1920x1080


def test_layout_fills_the_frame_by_default():
    # a small recording (a 1366x720 desktop window) is scaled up until it reaches the padding line
    st = Style(frame=True)
    lay = style.layout(st, (1366, 720))
    pad = st.padding * 1080
    assert lay["scale"] > 1.2
    assert lay["w"] >= 1920 - 2 * pad - 2 or lay["h"] >= 1080 - 2 * pad - 2
    assert style.layout(Style(frame=True), (300, 200))["scale"] == style.MAX_FILL  # capped


def test_layout_scales_down_for_a_square_canvas_and_leaves_room_for_the_bar():
    st = Style(frame=True, canvas=(1080, 1080), chrome=True)
    lay = style.layout(st, (1440, 900))
    assert lay["scale"] < 1 and lay["w"] <= 1080 - 2 * st.padding * 1080
    x, wy, w, h = lay["win"]
    assert h == lay["h"] + lay["bar"] and lay["y"] == wy + lay["bar"]
    assert all(v % 2 == 0 for v in (lay["w"], lay["h"], lay["x"], lay["y"]))


def test_frame_is_on_by_default_in_public_mode_only(tmp_path):
    assert load(build(tmp_path)).style.frame is True
    p = tmp_path / "h.yaml"
    d = yaml.safe_load(yaml.safe_dump(BASE))
    d.update(mode="handover", client="acme", auth="acme")
    p.write_text(yaml.safe_dump(d), encoding="utf-8")
    assert load(p).style.frame is False


def test_style_rejects_unknown_keys_and_loud_music(tmp_path):
    with pytest.raises(StoryboardError) as e:
        load(build(tmp_path, style={"musik": "ambient", "music_db": -6}))
    msg = "\n".join(e.value.errors)
    assert "style.musik: unknown key" in msg and "style.music_db" in msg


def test_zoom_values_and_style_default(tmp_path):
    steps = [
        {"id": "a", "action": "click", "target": "#a", "caption": {"n": 1, "title": "A"}, "narration": "One."},
        {"id": "b", "action": "click", "target": "#b", "zoom": False, "caption": {"n": 2, "title": "B"}, "narration": "Two."},
        {"id": "c", "action": "wait_for", "target": "#c", "zoom": "auto", "caption": {"n": 3, "title": "C"}, "narration": "Three."},
    ]
    sb = load(build(tmp_path, steps=steps, style={"zoom": 1.3}))
    assert [s.zoom for s in sb.steps] == [1.3, 0.0, 1.5]


def test_zoom_needs_something_to_zoom_to(tmp_path):
    steps = [{"id": "a", "action": "pause", "zoom": 2, "caption": {"n": 1, "title": "A"}, "narration": "One."}]
    with pytest.raises(StoryboardError) as e:
        load(build(tmp_path, steps=steps))
    assert any("zoom: needs something to zoom to" in x for x in e.value.errors)


def test_chrome_title_is_scanned_in_public_mode(tmp_path):
    with pytest.raises(StoryboardError) as e:
        load(build(tmp_path, style={"chrome": True, "chrome_title": "app.acme-internal.com"}))
    assert any("style.chrome_title" in x for x in e.value.errors)


def test_music_bed_level_and_ducking():
    sr = 8000
    m = music.bed("ambient", 30.0, sr, [(10.0, 20.0)], level_db=-28, duck_db=8)
    db = lambda x: 20 * np.log10(np.sqrt(np.mean(x ** 2)))
    between, under = m[int(4 * sr): int(9 * sr)], m[int(12 * sr): int(18 * sr)]
    assert abs(db(between) - -28) < 2.5
    assert 6 < db(between) - db(under) < 10


def test_folder_publish_writes_the_site_layout(tmp_path, monkeypatch):
    out = tmp_path / "out" / "demo"
    out.mkdir(parents=True)
    for f in publish.FILES:
        (out / f).write_bytes(b"x")
    (out / "timeline_out.json").write_text(json.dumps({"size": [1920, 1080]}), encoding="utf-8")
    monkeypatch.setattr(publish, "conf", lambda: {"target": "folder", "folder": str(tmp_path / "site")})
    sb = load(build(tmp_path))
    sb.name = "demo"
    res = publish.publish_public(sb, out, log=lambda *_: None)
    assert res["ok"] and res["target"] == "folder"
    site = tmp_path / "site" / "www"
    assert (site / "media" / "demo" / "video.mp4").exists() and (site / "v" / "demo" / "index.html").exists()
    assert json.loads((site / "videos.json").read_text())[0]["slug"] == "demo"
    assert 'property="og:' not in (site / "v" / "demo" / "index.html").read_text()  # no base_url: no share tags


def test_probe_reads_codec_size_and_duration_without_ffprobe(tmp_path):
    mp4 = tmp_path / "t.mp4"
    tools.ffmpeg("-f", "lavfi", "-i", "color=c=blue:s=320x240:d=1.5", "-f", "lavfi", "-i", "sine=d=1.5",
                 "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(mp4))
    p = tools.probe(mp4)
    assert p["video"] == {"codec": "h264", "width": 320, "height": 240}
    assert p["audio"]["codec"] == "aac" and abs(p["duration"] - 1.5) < 0.1


def test_variant_overrides_settings_but_keeps_the_steps(tmp_path):
    p = build(tmp_path, variants={"square": {"viewport": [960, 960], "style": {"canvas": [1080, 1080]}}},
              style={"background": "ocean"})
    base, sq = load(p), load(p, variant="square")
    assert sq.name == "test-sb-square" and sq.viewport == (960, 960)
    assert sq.style.canvas == (1080, 1080) and sq.style.background == "ocean"  # style merges
    assert [s.id for s in sq.steps] == [s.id for s in base.steps]
    with pytest.raises(StoryboardError):
        load(p, variant="vertical")


def test_background_auto_rotates_by_name_and_respects_categories():
    names = [f"video-{i}" for i in range(40)]
    picks = {style.pick_background("auto", n) for n in names}
    assert len(picks) > 8                                         # videos get different wallpapers
    assert style.pick_background("auto", "a") == style.pick_background("auto", "a")  # re-renders match
    assert all(style.BACKGROUNDS[style.pick_background("purple", n)][0] == "purple" for n in names)
    assert style.pick_background(["ocean", "mint"], "x") in ("ocean", "mint")
    assert style.pick_background("#123456", "x") == "#123456"


def test_viewport_auto_fills_the_canvas_at_1to1(tmp_path):
    sb = load(build(tmp_path, viewport="auto", style={"subtitles": True}))
    lay = style.layout(sb.style, sb.viewport)
    assert lay["scale"] == 1.0 and (lay["w"], lay["h"]) == tuple(sb.viewport)
    assert lay["x"] <= 0.05 * 1080 and sb.viewport[0] > 1800


def test_voice_picks_male_or_female_and_validates(tmp_path):
    from demo_studio.tts import VOICE_POOLS
    assert load(build(tmp_path, voice="male")).voice in VOICE_POOLS["male"]
    assert load(build(tmp_path, voice="female")).voice in VOICE_POOLS["female"]
    picks = {load(build(tmp_path, voice="auto", name=f"video-{i}")).voice for i in range(12)}
    assert picks & set(VOICE_POOLS["male"]) and picks & set(VOICE_POOLS["female"])  # both kinds across videos
    assert load(build(tmp_path, voice="bm_george")).voice == "bm_george"
    with pytest.raises(StoryboardError):
        load(build(tmp_path, voice="xx_nobody"))


def test_a_step_can_have_its_own_narrator(tmp_path):
    steps = [
        {"id": "a", "action": "pause", "caption": {"n": 1, "title": "A"}, "narration": "One.", "voice": "am_michael"},
        {"id": "b", "action": "pause", "caption": {"n": 2, "title": "B"}, "narration": "Two."},
    ]
    sb = load(build(tmp_path, steps=steps, voice="af_heart"))
    assert sb.voice_for("a") == "am_michael" and sb.voice_for("b") == "af_heart" and sb.voice_for("_intro") == "af_heart"


def test_desktop_selectors_and_storyboard(tmp_path):
    from demo_studio.desktop import SelectorError, parse_selector
    assert parse_selector("name=Save; type=Button") == {"title": "Save", "control_type": "Button"}
    assert parse_selector("id=CalculatorResults; index=1") == {"auto_id": "CalculatorResults", "found_index": 1}
    assert parse_selector("at=640, 360") == {"at": (640, 360)}
    for bad in ("Save", "label=Save", "at=x,y"):
        with pytest.raises(SelectorError):
            parse_selector(bad)
    steps = [{"id": "a", "action": "click", "target": "name=Seven; type=Button", "caption": {"n": 1, "title": "A"},
              "narration": "One."},
             {"id": "b", "action": "key", "keys": "^s", "caption": {"n": 2, "title": "B"}, "narration": "Two."}]
    sb = load(build(tmp_path, driver="desktop", app={"window": "^Calculator$"}, base_url=None, steps=steps))
    assert sb.driver == "desktop" and sb.steps[1].keys == "^s"
    with pytest.raises(StoryboardError) as e:
        load(build(tmp_path, driver="desktop", base_url=None,
                   steps=[dict(steps[0], target="Seven", route="/x")]))
    msg = "\n".join(e.value.errors)
    assert "app.window" in msg and "steps.a.target" in msg and "routes are for the browser" in msg
