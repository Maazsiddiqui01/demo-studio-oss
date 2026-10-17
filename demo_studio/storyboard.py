"""Load a storyboard YAML and enforce the rules in docs/storyboard-format.md and docs/modes-and-privacy.md."""
from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import textscan

ACTIONS = {"click", "type", "wait_for", "scroll", "goto", "pause", "hover", "key"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
# On a live system, a click on a control with one of these words may write data.
RISKY_WORDS = re.compile(
    r"\b(apply|send|delete|remove|save|submit|confirm|approve|decline|reject|archive|create|update|"
    r"publish|post|merge|import|sync|run|undo|restore|pay|charge|invite|disconnect|revoke|reset)\b",
    re.IGNORECASE,
)
# Desktop key steps that may save, delete or submit (pywinauto syntax: ^ is Ctrl, ~ is Enter).
RISKY_KEYS = re.compile(r"\^\+?s\b|\{(DEL|DELETE|ENTER|BACKSPACE|BKSP|BS)[ }]|~|%\{F4\}", re.IGNORECASE)


THEMES = ("petrol", "kinetic", "navy")
CAPTIONS = ("card", "pill", "lower")
INTRO_LAYOUTS = ("statement", "product", "agenda", "cinematic")
OUTRO_LAYOUTS = ("summary", "cta", "cinematic")
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")

LOCAL_URL = re.compile(r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?(/|$)", re.IGNORECASE)


class StoryboardError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("\n".join(errors))
        self.errors = errors


@dataclass
class Caption:
    n: int
    title: str
    sub: str = ""


@dataclass
class Step:
    id: str
    action: str
    caption: Caption
    narration: str
    route: str | None = None
    target: str | None = None
    text: str | None = None
    wait_for: str | None = None
    timeout: float = 30.0
    highlight: str | None = None
    speed_up: bool = False
    speed_factor: float = 4.0
    live_write: bool = False
    confirmed_by_owner: bool = False
    hold: float = 0.0
    scroll_by: int = 0
    keys: str | None = None     # action key: a shortcut such as "^s" or "{ENTER}" (desktop driver)
    zoom: float = 0.0           # 0 = no zoom; otherwise the scale (zoom: auto is 1.5)
    zoom_on: str | None = None  # what to zoom to (default: target, then highlight)
    zoom_set: bool = False      # the step sets zoom itself (an explicit zoom: false beats style.zoom)
    voice: str | None = None    # this step's narrator, when it differs from the video's voice


@dataclass
class Style:
    """The framed look (demo_studio/style.py) and the music bed. On by default in public mode."""
    frame: bool = False
    canvas: tuple[int, int] = (1920, 1080)
    background: Any = "auto"    # a preset, a category, auto, a list of presets, CSS, or an image path
    padding: float = 0.04       # space around the window, as a fraction of the canvas
    radius: int = 18
    corners: str = "squircle"   # squircle | round
    border: bool = False        # a thin light border around the window
    fill: Any = "auto"          # auto: a smaller recording is scaled up to fill the frame (up to 2x);
                                # true: no limit; false: never above 1:1 (pixel-exact, more wallpaper)
    motion: str = "drift"       # drift (the wallpaper pans slowly) | none
    shadow: bool = True
    chrome: bool = False
    chrome_title: str = ""
    zoom: float = 0.0           # default zoom for click, type and hover steps (0 = off)
    music: str | None = None    # "ambient" or a file you have the rights to
    music_db: float = -28.0     # music level between narration lines (RMS dBFS)
    duck_db: float = 8.0        # how much lower it plays under narration
    theme: str = "petrol"       # slides, captions and ring: petrol | kinetic | navy
    accent: str | None = None   # "#RRGGBB" in place of the theme's accent and ring colour
    captions: str = "card"      # step captions: card | pill | lower
    subtitles: bool = False     # burn the narration into the video (for feeds that autoplay muted)


@dataclass
class Storyboard:
    path: Path
    version: int
    name: str
    mode: str
    title: str
    eyebrow: str
    base_url: str
    voice: str
    sources: list[str]
    steps: list[Step]
    client: str | None = None
    intro_note: str | None = None
    intro_narration: str | None = None
    outro_heading: str = ""
    outro_bullets: list[str] = field(default_factory=list)
    outro_narration: str | None = None
    outro_cta: str | None = None        # a link or command on the closing slide (cta layout)
    intro_layout: str = "auto"          # statement | product | agenda | cinematic | auto
    outro_layout: str = "auto"          # summary | cta | cinematic | auto
    login_url: str | None = None
    auth: str | None = None
    seeded_test_data: bool = False
    # A private copy of the client's app on this PC (localhost), filled with made-up data:
    # no live system is recorded, so writes are allowed and no saved sign-in is needed.
    local_copy: bool = False
    navigation: str = "load"
    driver: str = "browser"             # browser (Playwright) | desktop (any Windows app window)
    app: dict[str, Any] = field(default_factory=dict)   # desktop: window (title regex), launch, size
    speed: float = 1.0
    viewport: tuple[int, int] = (1440, 900)
    poster: str = "intro"
    banned_terms: list[str] = field(default_factory=list)
    allowed_hosts: list[str] = field(default_factory=list)
    redact_selectors: list[str] = field(default_factory=list)
    redact_patterns: list[str] = field(default_factory=list)
    delivery: dict[str, Any] = field(default_factory=dict)
    cutdown: dict[str, Any] | None = None
    style: Style = field(default_factory=Style)
    raw: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    variant: str | None = None   # the `variants:` entry this was built from (for example "square")

    # -- text -------------------------------------------------------------
    def on_screen_texts(self) -> list[tuple[str, str]]:
        """Every string we put on screen or in the voice track, with where it comes from."""
        out = [("title", self.title), ("eyebrow", self.eyebrow)]
        if self.intro_note:
            out.append(("intro_note", self.intro_note))
        if self.intro_narration:
            out.append(("intro.narration", self.intro_narration))
        if self.outro_heading:
            out.append(("outro.heading", self.outro_heading))
        for i, b in enumerate(self.outro_bullets):
            out.append((f"outro.bullets[{i}]", b))
        if self.outro_narration:
            out.append(("outro.narration", self.outro_narration))
        if self.outro_cta:
            out.append(("outro.cta", self.outro_cta))
        if self.style.frame and self.style.chrome and self.style.chrome_title:
            out.append(("style.chrome_title", self.style.chrome_title))
        for s in self.steps:
            out.append((f"{s.id}.caption.title", s.caption.title))
            if s.caption.sub:
                out.append((f"{s.id}.caption.sub", s.caption.sub))
            out.append((f"{s.id}.narration", s.narration))
        return out

    @property
    def plain_title(self) -> str:
        """The title without the *highlight* markup."""
        return self.title.replace("*", "")

    def layouts(self) -> tuple[str, str]:
        """The intro and outro layouts. `auto` picks one from the name, so different videos look
        different while a re-render of the same video looks the same."""
        h = int(hashlib.sha1(self.name.encode()).hexdigest(), 16)
        intro = self.intro_layout if self.intro_layout != "auto" else INTRO_LAYOUTS[h % len(INTRO_LAYOUTS)]
        if self.outro_layout != "auto":
            outro = self.outro_layout
        else:
            outro = "cta" if self.outro_cta else ("summary", "cinematic")[(h >> 8) % 2]
        return intro, outro

    def voice_for(self, line_id: str) -> str:
        """The voice that reads one narration line: the step's own voice, or the video's."""
        step = next((s for s in self.steps if s.id == line_id), None)
        return (step.voice if step and step.voice else None) or self.voice

    def narration_lines(self) -> list[tuple[str, str]]:
        lines = []
        if self.intro_narration:
            lines.append(("_intro", self.intro_narration))
        lines += [(s.id, s.narration) for s in self.steps]
        if self.outro_narration:
            lines.append(("_outro", self.outro_narration))
        return lines

    def derive_cutdown(self) -> "Storyboard":
        """The proposal cut-down: a subset of steps, renumbered, as its own storyboard."""
        if not self.cutdown:
            raise StoryboardError(["this storyboard has no cutdown block"])
        cd = self.cutdown
        sb = copy.deepcopy(self)
        wanted = cd["steps"]
        by_id = {s.id: s for s in sb.steps}
        sb.steps = [by_id[i] for i in wanted]
        for n, s in enumerate(sb.steps, 1):
            s.caption.n = n
            over = (cd.get("overrides") or {}).get(s.id) or {}
            if "narration" in over:
                s.narration = over["narration"]
            if "caption" in over:
                s.caption = Caption(n=n, title=over["caption"].get("title", s.caption.title),
                                    sub=over["caption"].get("sub", s.caption.sub))
            if s.speed_up and "(sped up)" not in s.caption.sub:
                s.caption.sub = (s.caption.sub + " (sped up)").strip()
        sb.name = cd.get("name", self.name + "-cut")
        for key, attr in (("title", "title"), ("intro_note", "intro_note")):
            if key in cd:
                setattr(sb, attr, cd[key])
        if "intro_narration" in cd:
            sb.intro_narration = cd["intro_narration"]
        if "outro" in cd:
            sb.outro_heading = cd["outro"].get("heading", sb.outro_heading)
            sb.outro_bullets = cd["outro"].get("bullets", sb.outro_bullets)
            sb.outro_narration = cd["outro"].get("narration", sb.outro_narration)
            sb.outro_cta = cd["outro"].get("cta", sb.outro_cta)
        if "poster" in cd:
            sb.poster = cd["poster"]
        sb.cutdown = None
        return sb


def _zoom(v: Any, where: str, errors: list[str]) -> float:
    if v in (None, False, 0, "off", "none"):
        return 0.0
    if v is True or v == "auto":
        return 1.5
    try:
        z = float(v)
    except (TypeError, ValueError):
        errors.append(f"{where}zoom: a number from 1.1 to 3, or auto")
        return 0.0
    if not 1.1 <= z <= 3.0:
        errors.append(f"{where}zoom: a number from 1.1 to 3, or auto")
        return 0.0
    return z


def _style(d: Any, mode: str, errors: list[str]) -> Style:
    d = d or {}
    if not isinstance(d, dict):
        errors.append("style: must be a mapping")
        d = {}
    known = set(Style.__dataclass_fields__)
    for k in d:
        if k not in known:
            errors.append(f"style.{k}: unknown key (one of {sorted(known)})")
    st = Style(frame=bool(d.get("frame", mode == "public")))
    if "canvas" in d:
        c = d["canvas"]
        if not (isinstance(c, (list, tuple)) and len(c) == 2 and all(isinstance(x, int) and 320 <= x <= 3840 for x in c)):
            errors.append("style.canvas: [width, height] in pixels, for example [1920, 1080] or [1080, 1080]")
        else:
            st.canvas = (int(c[0]), int(c[1]))
    if d.get("music") is False:
        d = {**d, "music": None}
    if isinstance(d.get("background"), list):
        st.background = [str(b) for b in d["background"]]
        d = {k: v for k, v in d.items() if k != "background"}
    for key, typ in (("background", str), ("chrome_title", str), ("music", str), ("theme", str),
                     ("accent", str), ("captions", str), ("corners", str), ("motion", str)):
        if d.get(key) is not None:
            setattr(st, key, typ(d[key]))
    for key in ("padding", "music_db", "duck_db"):
        if key in d:
            setattr(st, key, float(d[key]))
    for key in ("radius",):
        if key in d:
            setattr(st, key, int(d[key]))
    for key in ("shadow", "chrome", "subtitles", "border"):
        if key in d:
            setattr(st, key, bool(d[key]))
    if "fill" in d:
        st.fill = "auto" if str(d["fill"]).lower() == "auto" else bool(d["fill"])
    st.zoom = _zoom(d.get("zoom"), "style.", errors)
    if st.music in ("none", "off", ""):
        st.music = None
    from .style import BACKGROUNDS, CATEGORIES
    for b in (st.background if isinstance(st.background, list) else []):
        if b not in BACKGROUNDS:
            errors.append(f"style.background: {b!r} is not a preset (presets: {', '.join(sorted(BACKGROUNDS))})")
    if st.corners not in ("squircle", "round"):
        errors.append("style.corners: squircle or round")
    if st.motion not in ("drift", "none"):
        errors.append("style.motion: drift or none")
    if st.theme not in THEMES:
        errors.append(f"style.theme: one of {', '.join(THEMES)}")
    if st.captions not in CAPTIONS:
        errors.append(f"style.captions: one of {', '.join(CAPTIONS)}")
    if st.accent is not None and not HEX.match(st.accent):
        errors.append("style.accent: a colour like \"#FF5A1F\"")
    if not 0 <= st.padding < 0.3:
        errors.append("style.padding: a fraction of the canvas, 0 to 0.3")
    if st.music_db > -12:
        errors.append("style.music_db: keep music at -12 dBFS or quieter so the voice stays clear")
    return st


def _req(d: dict, key: str, errors: list[str], where: str = "") -> Any:
    if key not in d or d[key] in (None, ""):
        errors.append(f"{where}{key}: required")
        return None
    return d[key]


MERGED_KEYS = ("style", "delivery", "intro", "outro", "redact")


def apply_variant(data: dict, variant: str) -> dict:
    """The storyboard with one `variants:` entry laid over it: same steps, other settings (for
    example a square canvas for social feeds). Mappings in MERGED_KEYS merge; other keys replace."""
    vs = data.get("variants") or {}
    if variant not in vs:
        raise StoryboardError([f"variants: no variant {variant!r} (have: {', '.join(vs) or 'none'})"])
    over = vs[variant] or {}
    if "steps" in over:
        raise StoryboardError([f"variants.{variant}: steps cannot change in a variant (use cutdown for fewer steps)"])
    out = {k: v for k, v in data.items() if k != "variants"}
    for k, v in over.items():
        if k in MERGED_KEYS and isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    out["name"] = over.get("name") or f"{data.get('name')}-{variant}"
    if isinstance(out.get("cutdown"), dict) and "cutdown" not in over:
        out["cutdown"] = {**out["cutdown"], "name": f"{out['name']}-cut"}
    return out


def load(path: str | Path, variant: str | None = None) -> Storyboard:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise StoryboardError([f"{path}: not a YAML mapping"])
    if variant:
        data = apply_variant(data, variant)
    errors: list[str] = []

    mode = data.get("mode")
    if mode not in ("public", "handover"):
        errors.append("mode: required, public or handover (the CLI refuses to render without it)")
    if data.get("version") != 1:
        errors.append("version: must be 1")
    name = _req(data, "name", errors)
    if name and not SLUG.match(name):
        errors.append("name: lowercase letters, digits and dashes only")

    steps: list[Step] = []
    raw_steps = data.get("steps") or []
    if not isinstance(raw_steps, list) or not raw_steps:
        errors.append("steps: at least one step is required")
        raw_steps = []
    seen = set()
    for i, rs in enumerate(raw_steps):
        w = f"steps[{i}]."
        if not isinstance(rs, dict):
            errors.append(f"{w}: must be a mapping")
            continue
        sid = _req(rs, "id", errors, w)
        if sid in seen:
            errors.append(f"{w}id: duplicate {sid!r}")
        seen.add(sid)
        action = rs.get("action")
        if action not in ACTIONS:
            errors.append(f"{w}action: one of {sorted(ACTIONS)}")
        if action in ("click", "type", "wait_for", "hover") and not rs.get("target"):
            errors.append(f"{w}target: required for {action}")
        if action == "key" and not rs.get("keys"):
            errors.append(f"{w}keys: required for key (for example \"^s\" or \"{{ENTER}}\")")
        if action == "type" and rs.get("text") is None:
            errors.append(f"{w}text: required for type")
        cap = rs.get("caption") or {}
        if not cap.get("title"):
            errors.append(f"{w}caption.title: required")
        narr = rs.get("narration")
        if not narr:
            errors.append(f"{w}narration: required")
        speed_up = bool(rs.get("speed_up", False))
        sub = cap.get("sub", "") or ""
        if speed_up and "(sped up)" not in sub:
            sub = (sub + " (sped up)").strip()
        step = Step(
            id=sid or f"step{i}",
            action=action or "pause",
            caption=Caption(n=int(cap.get("n", i + 1)), title=cap.get("title", ""), sub=sub),
            narration=narr or "",
            route=rs.get("route"),
            target=rs.get("target"),
            text=rs.get("text"),
            wait_for=rs.get("wait_for"),
            timeout=float(rs.get("timeout", 120 if speed_up else 30)),
            highlight=rs.get("highlight"),
            speed_up=speed_up,
            speed_factor=float(rs.get("speed_factor", 4.0)),
            live_write=bool(rs.get("live_write", False)),
            confirmed_by_owner=bool(rs.get("confirmed_by_owner", False)),
            hold=float(rs.get("hold", 0.0)),
            scroll_by=int(rs.get("scroll_by", 0)),
            keys=rs.get("keys"),
            zoom=_zoom(rs.get("zoom"), w, errors),
            zoom_on=rs.get("zoom_on"),
            zoom_set="zoom" in rs,
            voice=rs.get("voice"),
        )
        if step.speed_up and not step.wait_for and step.action != "wait_for":
            errors.append(f"{w}speed_up: needs a wait (action wait_for, or a wait_for selector)")
        if step.speed_factor < 1:
            errors.append(f"{w}speed_factor: must be 1 or more")
        if step.zoom and not (step.zoom_on or step.target or step.highlight):
            errors.append(f"{w}zoom: needs something to zoom to (target, highlight or zoom_on)")
        if step.live_write and not step.confirmed_by_owner:
            errors.append(f"{w}live_write: true also needs confirmed_by_owner: true")
        steps.append(step)

    for i, s in enumerate(steps, 1):
        if s.caption.n != i:
            errors.append(f"steps: caption numbers must run 1..{len(steps)} in order ({s.id} has {s.caption.n})")
            break

    intro = data.get("intro") or {}
    outro = data.get("outro") or {}
    redact = data.get("redact") or {}
    delivery = data.get("delivery") or {}
    vp = data.get("viewport") or [1440, 900]
    if vp == "auto":
        vp = [1440, 900]  # replaced below, once the style (canvas, padding) is known

    sb = Storyboard(
        path=path,
        version=data.get("version", 0),
        name=name or "unnamed",
        mode=mode or "",
        title=data.get("title") or "",
        eyebrow=data.get("eyebrow") or "",
        base_url=(data.get("base_url") or "").rstrip("/"),
        voice=str(data.get("voice") or "af_heart") if not isinstance(data.get("voice"), list) else "af_heart",
        sources=list(data.get("sources") or []),
        steps=steps,
        client=data.get("client"),
        intro_note=data.get("intro_note"),
        intro_narration=intro.get("narration"),
        outro_heading=outro.get("heading", ""),
        outro_bullets=list(outro.get("bullets") or []),
        outro_narration=outro.get("narration"),
        outro_cta=outro.get("cta"),
        intro_layout=str(intro.get("layout") or "auto"),
        outro_layout=str(outro.get("layout") or "auto"),
        login_url=data.get("login_url"),
        auth=data.get("auth"),
        seeded_test_data=bool(data.get("seeded_test_data", False)),
        local_copy=bool(data.get("local_copy", False)),
        navigation=data.get("navigation", "load"),
        driver=str(data.get("driver") or "browser"),
        app=dict(data.get("app") or {}),
        speed=float(data.get("speed", 1.0)),
        viewport=(int(vp[0]), int(vp[1])),
        poster=data.get("poster", "intro"),
        banned_terms=list(data.get("banned_terms") or []),
        allowed_hosts=list(data.get("allowed_hosts") or []),
        redact_selectors=list(redact.get("selectors") or []),
        redact_patterns=list(redact.get("patterns") or []),
        delivery=dict(delivery),
        cutdown=data.get("cutdown"),
        style=_style(data.get("style"), mode or "", errors),
        raw=data,
        variant=variant,
    )
    # voice: an id, female, male, auto or a list, resolved from the name (a variant gets its own pick)
    from .tts import ENGLISH_VOICES, VOICE_POOLS, pick_voice
    sb.voice = pick_voice(data.get("voice") or "af_heart", sb.name)
    for st in steps:
        if st.voice:
            st.voice = pick_voice(st.voice, f"{sb.name}/{st.id}")
    for where, v in [("voice", sb.voice)] + [(f"steps.{st.id}.voice", st.voice) for st in steps if st.voice]:
        if v not in ENGLISH_VOICES:
            errors.append(f"{where}: {v!r} is not an English Kokoro voice; use female, male, auto, or one of "
                          f"{', '.join(VOICE_POOLS['female'] + VOICE_POOLS['male'])} (all: docs/storyboard-format.md)")
    if data.get("viewport") == "auto" and sb.style.frame:
        from .style import auto_viewport
        sb.viewport = auto_viewport(sb.style)
    # style.zoom applies to pointer steps that do not set their own zoom
    for st in steps:
        if not st.zoom_set and sb.style.zoom and st.action in ("click", "type", "hover"):
            st.zoom = sb.style.zoom

    if not sb.title:
        errors.append("title: required")
    if sb.intro_layout not in INTRO_LAYOUTS + ("auto",):
        errors.append(f"intro.layout: one of {', '.join(INTRO_LAYOUTS)} or auto")
    if sb.outro_layout not in OUTRO_LAYOUTS + ("auto",):
        errors.append(f"outro.layout: one of {', '.join(OUTRO_LAYOUTS)} or auto")
    if sb.outro_layout == "cta" and not sb.outro_cta:
        errors.append("outro.layout cta: needs outro.cta (the link or command to show)")
    if sb.driver not in ("browser", "desktop"):
        errors.append("driver: browser or desktop")
    if sb.driver == "desktop":
        from .desktop import parse_selector, SelectorError
        if not sb.app.get("window"):
            errors.append("app.window: required for the desktop driver (a regular expression matching the window title)")
        for st in steps:
            for key in ("target", "highlight", "zoom_on", "wait_for"):
                val = getattr(st, key)
                if val:
                    try:
                        parse_selector(val)
                    except SelectorError as e:
                        errors.append(f"steps.{st.id}.{key}: {e}")
            if st.action == "goto" or st.route:
                errors.append(f"steps.{st.id}: routes are for the browser driver; open the screen with a click instead")
    elif not sb.base_url or sb.base_url.startswith("TODO"):
        errors.append("base_url: required")
    if not sb.sources or any(str(s).startswith("TODO") for s in sb.sources):
        errors.append("sources: list where every claim comes from (no TODO)")
    if sb.navigation not in ("load", "spa"):
        errors.append("navigation: load or spa")
    for p in sb.redact_patterns:
        try:
            re.compile(p)
        except re.error as e:
            errors.append(f"redact.patterns: {p!r} does not compile ({e})")

    if sb.local_copy and not LOCAL_URL.match(sb.base_url or ""):
        errors.append("local_copy: base_url must be http://localhost, 127.0.0.1 or [::1] (a copy on this PC, never a live system)")
    local = sb.local_copy and bool(LOCAL_URL.match(sb.base_url or ""))

    # -- mode rules ---------------------------------------------------------
    if sb.mode == "public":
        if sb.auth and not sb.seeded_test_data:
            errors.append("public mode: auth must be null unless seeded_test_data: true is declared")
        if delivery.get("private_link"):
            errors.append("public mode: private_link is for handover videos")
        for where, text in sb.on_screen_texts():
            for h in (textscan.find_banned(text, sb.banned_terms, where)
                      + textscan.find_contacts(text, where, sb.allowed_hosts)):
                errors.append(f"public mode: {h.safe()}")
    elif sb.mode == "handover":
        if not sb.auth and not local and sb.driver == "browser":
            errors.append("handover mode: auth is required (a session saved by `studio login <name>`)")
        if delivery.get("public"):
            errors.append("handover mode: delivery.public must be false")
        if not sb.client or not SLUG.match(str(sb.client)):
            errors.append("handover mode: client is required (a folder-safe slug)")
        if delivery.get("private_link") and not delivery.get("expires"):
            errors.append("handover mode: a private link needs delivery.expires")
        for s in ([] if local else sb.steps):
            if s.action in ("click", "type") and not s.live_write:
                probe = f"{s.target or ''} {s.text or ''}"
                if s.action == "type" or RISKY_WORDS.search(probe):
                    errors.append(
                        f"handover mode: step {s.id} may write to the live system ({s.action} on {s.target!r}); "
                        "mark it live_write: true with confirmed_by_owner: true, or make it read-only"
                    )
            if s.action == "key" and not s.live_write and RISKY_KEYS.search(s.keys or ""):
                errors.append(
                    f"handover mode: step {s.id} sends {s.keys!r}, which may save, delete or submit on the live "
                    "system; mark it live_write: true with confirmed_by_owner: true, or use another key"
                )
        if sb.driver == "desktop" and not local and any(
                str(s.target or "").startswith("at=") and s.action in ("click", "type") and not s.live_write
                for s in sb.steps):
            sb.warnings.append("handover mode: clicks by position (at=X,Y) cannot be checked for writes; "
                               "make sure each one only changes the view")

    # -- copy rules (both modes) -------------------------------------------
    for where, text in sb.on_screen_texts():
        for h in textscan.find_dashes(text, where):
            errors.append(f"copy: {h.safe()}")
        for h in textscan.find_hype(text, where):
            sb.warnings.append(f"copy: hype word {h.match!r} in {where}")

    if sb.cutdown:
        ids = {s.id for s in steps}
        missing = [i for i in sb.cutdown.get("steps", []) if i not in ids]
        if missing or not sb.cutdown.get("steps"):
            errors.append(f"cutdown.steps: unknown or empty ({missing})")
        if sb.mode != "public":
            errors.append("cutdown: proposal cut-downs are for public videos only")

    bg = sb.style.background
    if sb.style.frame and isinstance(bg, str) and Path(bg).suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
        if not (Path(bg) if Path(bg).is_absolute() else path.parent / bg).exists():
            errors.append(f"style.background: image {bg!r} not found (relative to the storyboard)")
    if sb.cutdown and not errors:
        try:
            cut = sb.derive_cutdown()
        except (KeyError, StoryboardError) as e:
            errors.append(f"cutdown: {e}")
        else:
            for where, text in cut.on_screen_texts():
                for h in textscan.find_dashes(text, where):
                    errors.append(f"cutdown copy: {h.safe()}")
                if sb.mode == "public":
                    for h in (textscan.find_banned(text, sb.banned_terms, where)
                              + textscan.find_contacts(text, where, sb.allowed_hosts)):
                        errors.append(f"cutdown, public mode: {h.safe()}")

    if errors:
        raise StoryboardError(errors)
    return sb
