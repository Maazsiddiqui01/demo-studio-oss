"""Desktop driver: record any Windows app window, the way record.py records a browser page.

The app is driven through Windows UI Automation (pywinauto) with real mouse movement and keys,
while ffmpeg captures the window's part of the screen (gdigrab, the real cursor included).
Captions, slides, the "sped up" badge, the highlight ring and click pulses are drawn afterwards with
the same overlay design (overlay.js and overlay.css, rendered as still images by Playwright) and
composited onto the capture; zoom is applied from the action log. The result is a list of
timestamped frames, so assemble.py adds the frame, subtitles, music and speed-ups exactly as it does
for a browser recording.

Windows only for now: pip install "demo-studio[desktop]". While it records it moves the real mouse
and types, so nobody should touch the machine.

Selectors: "name=Save; type=Button" (keys: name, name_re, type, id, class, index), or "at=640,360"
for a point in window pixels when a control has no accessible name.
"""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

from .config import CURSOR_MOVE, LEAD_IN, SLIDE_MIN, TAIL, ZOOM_MS
from .tools import ffmpeg, ffmpeg_exe, probe

FPS = 30
SELECTOR_KEYS = {"name": "title", "name_re": "title_re", "type": "control_type", "id": "auto_id",
                 "class": "class_name", "index": "found_index"}


class SelectorError(ValueError):
    pass


def parse_selector(sel) -> dict:
    """'name=Save; type=Button' -> pywinauto criteria; 'at=640,360' -> {'at': (640, 360)}."""
    s = str(sel).strip()
    if s.startswith("at="):
        try:
            x, y = [int(float(v)) for v in s[3:].split(",")]
        except ValueError:
            raise SelectorError(f"{s!r}: write at=X,Y in window pixels") from None
        return {"at": (x, y)}
    crit: dict = {}
    for part in s.split(";"):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SelectorError(f"{s!r}: use key=value pairs, for example name=Save; type=Button")
        k, v = (x.strip() for x in part.split("=", 1))
        if k not in SELECTOR_KEYS:
            raise SelectorError(f"{s!r}: unknown key {k!r} (name, name_re, type, id, class, index, or at=X,Y)")
        crit[SELECTOR_KEYS[k]] = int(v) if k == "index" else v
    if not crit:
        raise SelectorError(f"{s!r}: empty selector")
    return crit


# ---- Windows helpers -----------------------------------------------------------------------
def _require_windows() -> None:
    if sys.platform != "win32":
        raise RuntimeError("the desktop driver needs Windows for now (it uses Windows UI Automation)")
    try:
        import pywinauto  # noqa: F401
    except ImportError:
        raise RuntimeError('the desktop driver needs pywinauto: pip install "demo-studio[desktop]"') from None
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # physical pixels everywhere
    except Exception:
        pass


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


def _visible_bounds(hwnd: int) -> tuple[int, int, int, int]:
    """The window's visible frame (without the invisible resize borders), clamped to the main
    screen's work area, so the taskbar is never part of the recording."""
    r = _RECT()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    wa = _RECT()
    if not ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(wa), 0):  # SPI_GETWORKAREA
        wa.left, wa.top = 0, 0
        wa.right, wa.bottom = ctypes.windll.user32.GetSystemMetrics(0), ctypes.windll.user32.GetSystemMetrics(1)
    left, top = max(wa.left, r.left), max(wa.top, r.top)
    right, bottom = min(wa.right, r.right), min(wa.bottom, r.bottom)
    w, h = (right - left) // 2 * 2, (bottom - top) // 2 * 2
    return left, top, w, h


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _cursor() -> tuple[int, int]:
    p = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def _glide(x: int, y: int, secs: float) -> None:
    """Move the real cursor along an eased path, so the recording shows the movement."""
    x0, y0 = _cursor()
    n = max(2, int(secs * 60))
    for i in range(1, n + 1):
        e = 0.5 - 0.5 * math.cos(math.pi * i / n)
        ctypes.windll.user32.SetCursorPos(int(x0 + (x - x0) * e), int(y0 + (y - y0) * e))
        time.sleep(secs / n)


def _escape_keys(text: str) -> str:
    """Literal text for pywinauto.keyboard.send_keys (its special characters wrapped in braces)."""
    return "".join("{" + c + "}" if c in "+^%~(){}[]" else c for c in text)


def _rgba(png: Path) -> None:
    """Chrome saves a fully opaque screenshot as RGB. An image track must keep one pixel format,
    so such files are rewritten as RGBA (the colour type is byte 25 of a PNG: 6 is RGBA)."""
    data = png.read_bytes()
    if len(data) > 25 and data[25] != 6:
        tmp = png.with_name(png.stem + ".rgba.png")
        ffmpeg("-i", str(png), "-pix_fmt", "rgba", str(tmp))
        tmp.replace(png)


class _PROCESSENTRY32(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong), ("th32ProcessID", ctypes.c_ulong),
                ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", ctypes.c_ulong),
                ("cntThreads", ctypes.c_ulong), ("th32ParentProcessID", ctypes.c_ulong),
                ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong), ("szExeFile", ctypes.c_char * 260)]


def _pid(hwnd: int) -> int:
    pid = ctypes.c_ulong()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _process_family(pid: int) -> set[int]:
    """The app's process and every process it started (helpers such as a WebView draw its popups)."""
    k32 = ctypes.windll.kernel32
    k32.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    parents: dict[int, int] = {}
    try:
        e = _PROCESSENTRY32()
        e.dwSize = ctypes.sizeof(e)
        ok = k32.Process32First(ctypes.c_void_p(snap), ctypes.byref(e))
        while ok:
            parents[e.th32ProcessID] = e.th32ParentProcessID
            ok = k32.Process32Next(ctypes.c_void_p(snap), ctypes.byref(e))
    finally:
        k32.CloseHandle(ctypes.c_void_p(snap))
    fam, grew = {pid}, True
    while grew:
        grew = False
        for c, par in parents.items():
            if par in fam and c not in fam and c != 0:
                fam.add(c)
                grew = True
    return fam


def _class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(128)
    ctypes.windll.user32.GetClassNameW(hwnd, buf, 128)
    return buf.value


def _uia_session():
    """A UI Automation client for the guard thread (its own COM apartment, so it never shares the
    recorder's objects across threads)."""
    import comtypes
    import comtypes.client
    try:
        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)
    except OSError:
        pass
    U = comtypes.client.GetModule("UIAutomationCore.dll")
    uia = comtypes.client.CreateObject(U.CUIAutomation, interface=U.IUIAutomation)
    return uia, uia.CreateTrueCondition(), U.TreeScope_Children


def _uia_toplevel(session) -> list[int]:
    """Top-level window handles as UI Automation lists them: top of the z-order first, and including
    the shell's notification, Start and search surfaces, which the Win32 z-order walk leaves out."""
    uia, cond, scope = session
    arr = uia.GetRootElement().FindAll(scope, cond)
    return [int(arr.GetElement(i).CurrentNativeWindowHandle or 0) for i in range(arr.Length)]


def windows_over(target: int, region: tuple[int, int, int, int], family: set[int],
                 uia_order: list[int] | None = None) -> list[tuple[int, list[int], str]]:
    """Other apps' windows stacked above the target window that cover part of the recorded region:
    notifications, chat pop-ups, another app's dialog. Returns [(hwnd, [x, y, w, h] in region pixels,
    window class)]. The app's own menus and tooltips (its process, the processes it started, or windows
    it owns) do not count, nor do click-through overlays."""
    u32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
    u32.GetTopWindow.restype = ctypes.c_void_p
    u32.GetWindow.restype = ctypes.c_void_p
    u32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    rx, ry, rw, rh = region
    above: dict[int, bool] = {}  # hwnd -> listed by UI Automation (already visible and uncloaked)
    h = u32.GetTopWindow(None)
    while h and h != target:
        above[h] = False
        h = u32.GetWindow(h, 2)  # GW_HWNDNEXT: the next window down the z-order
    for h in uia_order or []:
        if h == target:
            break
        if h:
            above[h] = True
    found: list[tuple[int, list[int], str]] = []
    for h, from_uia in above.items():
        try:
            if not u32.IsWindowVisible(ctypes.c_void_p(h)) or u32.IsIconic(ctypes.c_void_p(h)):
                continue
            if not from_uia:
                cloaked = ctypes.c_int(0)
                dwm.DwmGetWindowAttribute(ctypes.c_void_p(h), 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
                if cloaked.value:
                    continue
            if u32.GetWindowLongW(ctypes.c_void_p(h), -20) & 0x20:  # WS_EX_TRANSPARENT: click-through overlay
                continue
            owner, own = u32.GetWindow(h, 4), False
            while owner:
                if owner == target:
                    own = True
                    break
                owner = u32.GetWindow(owner, 4)
            if own or _pid(h) in family:
                continue
            r = _RECT()
            if dwm.DwmGetWindowAttribute(ctypes.c_void_p(h), 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
                u32.GetWindowRect(ctypes.c_void_p(h), ctypes.byref(r))
            x0, y0 = max(r.left, rx), max(r.top, ry)
            x1, y1 = min(r.right, rx + rw), min(r.bottom, ry + rh)
            if x1 - x0 >= 8 and y1 - y0 >= 8:
                found.append((h, [x0 - rx, y0 - ry, x1 - x0, y1 - y0], _class_name(h)))
        except Exception:
            continue
    return found


def list_windows() -> list[dict]:
    _require_windows()
    from pywinauto import Desktop
    out = []
    for w in Desktop(backend="uia").windows():
        try:
            title = w.window_text()
            if title:
                out.append({"title": title, "rect": _visible_bounds(w.handle)})
        except Exception:
            continue
    return out


def inspect(pattern: str, depth: int = 6, limit: int = 400, log=print) -> None:
    """Print the window's controls with a selector for each, for writing storyboards."""
    _require_windows()
    win = _find_window(pattern)
    if not win:
        raise RuntimeError(f"no window matches {pattern!r} (`studio windows` lists them; Windows drops '&' from titles)")
    left, top, _, _ = _visible_bounds(win.handle)
    count = 0

    def walk(el, d):
        nonlocal count
        if d > depth or count >= limit:
            return
        for c in el.children():
            if count >= limit:
                return
            info = c.element_info
            r = info.rectangle
            sel = []
            if info.name:
                sel.append(f"name={info.name}")
            if info.control_type:
                sel.append(f"type={info.control_type}")
            if info.automation_id and not info.name:
                sel.append(f"id={info.automation_id}")
            log(f"{'  ' * d}{'; '.join(sel) or '(no name)'}   at {r.left - left},{r.top - top} {r.width()}x{r.height()}")
            count += 1
            walk(c, d + 1)

    log(f"window: {win.window_text()}")
    walk(win, 0)
    if count >= limit:
        log(f"(stopped at {limit} controls; use --depth or a narrower window)")


def _find_window(pattern: str):
    from pywinauto import Desktop
    for w in Desktop(backend="uia").windows():
        try:
            if re.search(pattern, w.window_text() or ""):
                return w
        except Exception:
            continue
    return None


# ---- the recorder ----------------------------------------------------------------------------
class DesktopRecorder:
    def __init__(self, sb, narr: dict, out: Path, log=print):
        self.sb, self.narr, self.out, self.log = sb, narr, out, log
        self.marks: list[dict] = []
        self.waits: list[dict] = []
        self.strings: list[dict] = []
        self.masked: list[dict] = []
        self.screen_ev: list[tuple[float, dict]] = []    # caption, badge, slide: drawn over the zoom
        self.content_ev: list[tuple[float, dict]] = []   # ring, pulse: drawn on the app, zoom with it
        self.blurs: list[dict] = []
        self.zooms: list[dict] = []
        self._screen = {"caption": None, "badge": None, "slide": None}
        self._content = {"ring": None, "pulse": None}
        self.zoomed: dict | None = None
        self.gen = 0  # each text scan opens a generation of blurs; a generation closes two scans later
        self.covers: list[dict] = []  # other apps' windows seen over the recording (blurred)
        self._guard_stop = None
        self.scan_secs = 1.0  # how long the last text scan took

    # -- overlay state ------------------------------------------------------------------------
    def scr(self, **kw) -> None:
        self._screen.update(kw)
        self.screen_ev.append((time.time(), dict(self._screen)))

    def con(self, **kw) -> None:
        self._content.update(kw)
        self.content_ev.append((time.time(), dict(self._content)))

    def rel(self, rect) -> list[int]:
        x, y, w, h = rect
        return [int(x - self.rx), int(y - self.ry), int(w), int(h)]

    # -- window and capture -------------------------------------------------------------------
    def open_window(self):
        app = self.sb.app
        win = _find_window(app["window"])
        if not win and app.get("launch"):
            self.log(f"  starting {app['launch']}")
            subprocess.Popen(app["launch"], shell=True)
            deadline = time.time() + float(app.get("launch_timeout", 90))
            while not win and time.time() < deadline:
                time.sleep(1)
                win = _find_window(app["window"])
        if not win:
            raise RuntimeError(f"no window matches app.window {app['window']!r}: open the app first, or set "
                               "app.launch (`studio windows` lists the open windows)")
        try:
            if win.is_minimized():
                win.restore()
        except Exception:
            pass
        if app.get("maximize"):
            win.maximize()
        elif app.get("size"):
            w, h = app["size"]
            pos = app.get("position", [0, 0])
            ctypes.windll.user32.MoveWindow(win.handle, int(pos[0]), int(pos[1]), int(w), int(h), True)
        win.set_focus()
        time.sleep(0.8)
        from pywinauto import Desktop
        return Desktop(backend="uia").window(handle=win.handle)  # a specification: it can search inside

    def start_capture(self) -> None:
        x, y, w, h = self.rx, self.ry, self.size[0], self.size[1]
        cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-f", "gdigrab", "-framerate", str(FPS),
               "-draw_mouse", "1", "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}", "-i", "desktop",
               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "10", "-pix_fmt", "yuv420p",
               str(self.out / "capture.mkv")]
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1.2)
        if self.proc.poll() is not None:
            raise RuntimeError("screen capture failed to start: " + self.proc.stderr.read().decode(errors="replace")[-400:])

    def start_guard(self) -> None:
        """Watch the z-order while recording: any other app's window over the region (a notification,
        a chat pop-up) is blurred from the moment it appears until it goes, padded in space and time."""
        import threading
        target = self.win.handle
        region = (self.rx, self.ry, self.size[0], self.size[1])
        stop = threading.Event()
        self._guard_stop = stop

        def loop():
            family, t_fam, open_ = _process_family(_pid(target)), time.time(), {}
            try:
                uia = _uia_session()
            except Exception as e:
                uia = None
                self.log(f"  note: the window guard runs without UI Automation ({e}); notifications may not be caught")
            while not stop.is_set():
                now = time.time()
                if now - t_fam > 2:
                    family, t_fam = _process_family(_pid(target)), now
                try:
                    order = _uia_toplevel(uia) if uia else None
                except Exception:
                    order = None
                seen = set()
                for h, rect, cls in windows_over(target, region, family, order):
                    seen.add(h)
                    c = open_.get(h)
                    if c is None:
                        c = open_[h] = {"rect": rect, "t0": now, "t1": None, "cls": cls}
                        self.covers.append(c)
                    else:
                        x0, y0 = min(c["rect"][0], rect[0]), min(c["rect"][1], rect[1])
                        x1 = max(c["rect"][0] + c["rect"][2], rect[0] + rect[2])
                        y1 = max(c["rect"][1] + c["rect"][3], rect[1] + rect[3])
                        c["rect"] = [x0, y0, x1 - x0, y1 - y0]
                for h in list(open_):
                    if h not in seen:
                        open_.pop(h)["t1"] = now
                stop.wait(0.08)
            for c in open_.values():
                c["t1"] = time.time()

        self._guard = threading.Thread(target=loop, daemon=True)
        self._guard.start()

    def stop_guard(self) -> None:
        if self._guard_stop:
            self._guard_stop.set()
            self._guard.join(timeout=2)
        w, h = self.size
        for c in self.covers:
            x, y, cw, ch = c["rect"]
            x0, y0 = max(0, x - 8), max(0, y - 8)
            x1, y1 = min(w, x + cw + 8), min(h, y + ch + 8)
            self.blurs.insert(0, {"rect": [x0, y0, x1 - x0, y1 - y0], "t0": c["t0"] - 0.3,
                                  "t1": (c["t1"] or time.time()) + 0.3,
                                  "why": "another app's window", "gen": -1, "strong": True})
            self.masked.append({"where": "screen", "why": "another app's window over the recording",
                                "tag": c["cls"].lower()})
        if self.covers:
            self.log(f"  blurred {len(self.covers)} other app window(s) that covered the recording "
                     f"({', '.join(sorted({c['cls'] for c in self.covers}))})")
        if any(c["rect"][2] * c["rect"][3] > 0.5 * w * h for c in self.covers):
            self.log("  warning: another app's window covered most of the recording; check the frames, "
                     "and turn on Do Not Disturb or close that app before recording")

    def stop_capture(self) -> tuple[float, float]:
        t_stop = time.time()
        try:
            self.proc.communicate(input=b"q", timeout=60)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        dur = float(probe(self.out / "capture.mkv")["duration"] or 0)
        if dur <= 0:
            raise RuntimeError("the screen capture is empty")
        return t_stop - dur, dur

    def still(self) -> str:
        """A screenshot of the window, for the product intro layout."""
        p = self.out / "window.jpg"
        ffmpeg("-f", "gdigrab", "-offset_x", str(self.rx), "-offset_y", str(self.ry), "-video_size",
               f"{self.size[0]}x{self.size[1]}", "-i", "desktop", "-frames:v", "1", "-q:v", "3", str(p))
        return "data:image/jpeg;base64," + base64.b64encode(p.read_bytes()).decode()

    # -- finding and acting -------------------------------------------------------------------
    def locate(self, sel: str, timeout: float = 15):
        """Returns (wrapper or None, screen rect x, y, w, h)."""
        from pywinauto.findwindows import ElementAmbiguousError
        c = parse_selector(sel)
        if "at" in c:
            x, y = c["at"]
            return None, (self.rx + x - 1, self.ry + y - 1, 2, 2)
        deadline = time.time() + timeout
        while True:
            try:
                spec = self.win.child_window(**c)
                if spec.exists(timeout=0.3):
                    wr = spec.wrapper_object()
                    r = wr.rectangle()
                    if r.width() > 0 and r.height() > 0:
                        return wr, (r.left, r.top, r.width(), r.height())
            except ElementAmbiguousError:
                c = {**c, "found_index": 0}
                continue
            except Exception:
                pass
            if time.time() > deadline:
                raise RuntimeError(f"{sel!r} was not found in the window within {timeout:.0f}s "
                                   "(`studio inspect` lists its controls)")
            time.sleep(0.25)

    def hold_until(self, t_start: float, need: float) -> None:
        while True:
            now = time.time()
            saved = sum((min(w["end"] or now, now) - max(w["start"], t_start)) * (1 - 1 / w["factor"])
                        for w in self.waits if (w["end"] or now) > t_start)
            left = need - ((now - t_start) - saved)
            if left <= 0:
                return
            time.sleep(min(left, 0.2))

    def zoom_to(self, rect, scale: float) -> None:
        if self.zoomed:
            self.zoom_out()
        self.zoomed = {"rect": self.rel(rect), "scale": scale, "t_in": time.time(), "t_out": None}
        self.zooms.append(self.zoomed)
        time.sleep(ZOOM_MS / 1000 + 0.05)

    def zoom_out(self) -> None:
        if self.zoomed:
            self.zoomed["t_out"] = time.time()
            self.zoomed = None
            time.sleep(ZOOM_MS / 1000 + 0.05)

    def wait_visible(self, step, sel: str) -> None:
        if step.speed_up:
            self.scr(badge=f"Sped up {step.speed_factor:g}x")
        w = {"step": step.id, "start": time.time(), "end": None, "factor": step.speed_factor if step.speed_up else 1.0}
        if step.speed_up:
            self.waits.append(w)
        try:
            self.locate(sel, timeout=step.timeout)
        finally:
            w["end"] = time.time()
            if step.speed_up:
                self.scr(badge=None)

    def point_and(self, step) -> None:
        from pywinauto import keyboard, mouse
        _, rect = self.locate(step.target)
        x, y, w, h = rect
        cx, cy = int(x + w / 2), int(y + h / 2)
        if step.zoom:
            zr = self.locate(step.zoom_on)[1] if step.zoom_on else rect
            self.zoom_to(zr, step.zoom)
        if w > 2:
            self.con(ring=self.rel(rect))
        _glide(cx, cy, CURSOR_MOVE)
        time.sleep(0.15)
        if step.action == "hover":
            return
        if step.action in ("click", "type"):
            mouse.click(button="left", coords=(cx, cy))
            for i, sc in enumerate((0.3, 0.8, 1.3, None)):
                self.con(pulse=None if sc is None else [cx - self.rx, cy - self.ry, sc])
                time.sleep(0.09)
        if step.action == "type" and step.text is not None:
            keyboard.send_keys(_escape_keys(step.text), with_spaces=True, pause=0.05)
        time.sleep(0.3)

    # -- privacy and the text scan ------------------------------------------------------------
    def collect(self, where: str, t_from: float) -> None:
        from .record import DEFAULT_REDACT_PATTERNS
        pats = [re.compile(p, re.I) for p in DEFAULT_REDACT_PATTERNS + list(self.sb.redact_patterns)]
        texts, values, found = [], [], []
        t0 = time.time()
        try:
            for el in self.win.descendants():
                if time.time() - t0 > 3 or len(texts) > 3000:
                    break
                info = el.element_info
                r = info.rectangle
                rect = [r.left - self.rx, r.top - self.ry, r.width(), r.height()]
                if rect[2] <= 0 or rect[3] <= 0:
                    continue
                try:
                    if info.element.CurrentIsOffscreen:  # hidden tabs and views are not on screen
                        continue
                except Exception:
                    pass
                try:
                    is_pw = bool(info.element.CurrentIsPassword)
                except Exception:
                    is_pw = False
                if is_pw:
                    found.append((rect, "password field", info.control_type))
                    continue
                name = info.name or ""
                val = ""
                # an edit box shows its value; a web view's Document value is its address, not on screen
                if info.control_type == "Edit":
                    try:
                        val = el.iface_value.CurrentValue or ""
                    except Exception:
                        val = ""
                if any(p.search(t) for p in pats for t in (name, val) if t):
                    found.append((rect, "pattern", info.control_type))
                # container names (a web view's "<address> - Web content") are labels, not drawn text
                if name and info.control_type not in ("Pane", "Document"):
                    texts.append(name)
                if val:
                    values.append(val)
        except Exception as e:
            self.log(f"  text scan skipped at {where}: {e}")
        for sel in self.sb.redact_selectors:
            try:
                found.append((self.rel(self.locate(sel, timeout=0.5)[1]), "selector", sel))
            except Exception:
                pass
        now = time.time()
        for b in self.blurs:
            if b["t1"] is None and b["gen"] < self.gen - 1:
                b["t1"] = now
        for rect, why, tag in found:
            self.blurs.append({"rect": rect, "t0": t_from, "t1": None, "why": why, "gen": self.gen})
            self.masked.append({"where": where, "why": why, "tag": str(tag).lower()})
        clean = lambda s: re.sub("|".join(f"(?:{p.pattern})" for p in pats), "[masked]", s, flags=re.I) if pats else s
        self.strings.append({"where": where, "url": "", "title": clean(self.win.window_text() or ""),
                             "text": clean("\n".join(texts)), "values": [clean(v) for v in values], "attrs": []})
        self.gen += 1

    # -- main ---------------------------------------------------------------------------------
    def run(self) -> dict:
        sb = self.sb
        self.win = self.open_window()
        self.rx, self.ry, w, h = _visible_bounds(self.win.handle)
        self.size = (w, h)
        self.log(f"  window {self.win.window_text()!r} at {self.rx},{self.ry}, {w}x{h}")
        intro_layout, outro_layout = sb.layouts()
        intro = {"kind": "intro", "layout": intro_layout, "eyebrow": sb.eyebrow, "title": sb.title,
                 "note": sb.intro_note or "", "count": len(sb.steps), "steps": [s.caption.title for s in sb.steps]}
        if intro_layout == "product":
            intro.update(shot=self.still(), shotRatio=round(w / h, 4))
        t_scan = time.time()
        self.collect("intro", t_scan)
        self.scan_secs = min(4.0, max(0.3, time.time() - t_scan))
        self.scr(slide=intro)
        self.start_capture()
        self.start_guard()
        t_rec = time.time()

        t0 = time.time()
        n = self.narr.get("_intro", {}).get("seconds", 0)
        self.hold_until(t0, max(SLIDE_MIN, LEAD_IN + n + TAIL) if n else SLIDE_MIN)
        self.marks.append({"id": "_intro", "kind": "slide", "start": t0, "end": time.time()})
        self.scr(slide=None)
        time.sleep(0.4)

        total = len(sb.steps)
        for step in sb.steps:
            t_start = time.time()
            self.log(f"  step {step.caption.n} {step.id}")
            self.con(ring=None, pulse=None)
            # the caption changes as the step starts; a zoom-out from the last step plays meanwhile
            self.scr(caption={"n": step.caption.n, "total": total, "title": step.caption.title, "sub": step.caption.sub})
            if self.zoomed and not step.zoom:
                self.zoom_out()
            if step.highlight:
                self.con(ring=self.rel(self.locate(step.highlight, timeout=step.timeout)[1]))
            if step.action == "wait_for":
                self.wait_visible(step, step.target)
            elif step.action in ("click", "type", "hover"):
                self.point_and(step)
            elif step.action == "key":
                from pywinauto import keyboard
                keyboard.send_keys(step.keys, pause=0.05)
                time.sleep(0.3)
            elif step.action == "scroll":
                from pywinauto import mouse
                rect = self.locate(step.target)[1] if step.target else (self.rx + w // 2, self.ry + h // 2, 1, 1)
                _glide(int(rect[0] + rect[2] / 2), int(rect[1] + rect[3] / 2), CURSOR_MOVE)
                mouse.scroll(coords=(int(rect[0] + rect[2] / 2), int(rect[1] + rect[3] / 2)),
                             wheel_dist=-max(1, int((step.scroll_by or 360) / 120)))
                time.sleep(0.9)
            if step.wait_for:
                self.wait_visible(step, step.wait_for)
            if step.zoom and step.action not in ("click", "type", "hover") and (step.zoom_on or step.highlight or step.target):
                self.zoom_to(self.locate(step.zoom_on or step.highlight or step.target)[1], step.zoom)
            n = self.narr[step.id]["seconds"]
            need = LEAD_IN + n + TAIL + step.hold
            # the text scan reads the window through UI Automation, which takes a second or two in a
            # big app: it runs inside the step's last moments, so it adds no silence
            self.hold_until(t_start, need - self.scan_secs)
            t_scan = time.time()
            self.collect(step.id, t_start)
            self.scan_secs = min(4.0, max(0.3, time.time() - t_scan))
            self.hold_until(t_start, need)
            self.marks.append({"id": step.id, "kind": "step", "start": t_start, "end": time.time()})

        t0 = time.time()
        self.zoom_out()
        self.con(ring=None, pulse=None)
        outro = {"kind": "outro", "layout": outro_layout, "eyebrow": sb.eyebrow, "heading": sb.outro_heading,
                 "bullets": sb.outro_bullets, "cta": sb.outro_cta}
        self.scr(caption=None, slide=outro)
        n = self.narr.get("_outro", {}).get("seconds", 0)
        self.hold_until(t0, max(SLIDE_MIN + 1.0, LEAD_IN + n + TAIL + 0.6))
        t_end = time.time()
        self.marks.append({"id": "_outro", "kind": "slide", "start": t0, "end": t_end})
        time.sleep(0.3)
        t_cap0, dur = self.stop_capture()
        for b in self.blurs:
            b["t1"] = b["t1"] or t_end
        self.stop_guard()

        frames = self.compose(t_cap0, dur)
        return {"storyboard": str(Path(sb.path).resolve()), "name": sb.name, "mode": sb.mode, "variant": sb.variant,
                "driver": "desktop", "viewport": [w, h], "recorded_at": t_rec, "start": frames[0][0], "end": t_end,
                "marks": self.marks, "waits": self.waits, "frames": frames, "clock_offset": 0.0}

    # -- compositing --------------------------------------------------------------------------
    def render_states(self, events, kind: str, page, d: Path) -> list[tuple[float, str]]:
        """One transparent PNG per distinct overlay state; returns [(wall time, png name)]."""
        cache: dict[str, str] = {}
        out = []
        for t, st in events:
            key = hashlib.sha1(json.dumps(st, sort_keys=True).encode()).hexdigest()[:12]
            if key not in cache:
                if kind == "screen":
                    page.evaluate("async (s) => { const d = window.__ds; d.badge(s.badge); "
                                  "if (s.caption) { d.captionOff(); await d.caption(s.caption); } else d.captionOff(); "
                                  "await d.slide(s.slide); }", st)
                else:
                    page.evaluate("(s) => { const d = window.__ds; s.ring ? d.ringBox(...s.ring, 6) : d.ringBox(); "
                                  "s.pulse ? d.pulseAt(...s.pulse) : d.pulseAt(); }", st)
                name = f"{kind}-{key}.png"
                page.screenshot(path=str(d / name), omit_background=True)
                _rgba(d / name)
                cache[key] = name
            out.append((t, cache[key]))
        return out

    def compose(self, t_cap0: float, dur: float) -> list[list]:
        from playwright.sync_api import sync_playwright
        from .record import init_script
        w, h = self.size
        d = self.out / "overlay"
        d.mkdir(exist_ok=True)
        for old in d.glob("*.png"):
            old.unlink()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=["--force-color-profile=srgb"])
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
            page.set_content("<html><body style='margin:0;background:transparent'></body></html>")
            page.add_script_tag(content=init_script(self.sb))
            page.evaluate("() => window.__ds.still()")
            screen = self.render_states(self.screen_ev, "screen", page, d)
            page.evaluate("async () => { window.__ds.captionOff(); window.__ds.badge(null); await window.__ds.slide(null); }")
            content = self.render_states(self.content_ev or [(t_cap0, {"ring": None, "pulse": None})], "content", page, d)
            page.screenshot(path=str(d / "blank.png"), omit_background=True)
            browser.close()

        def ffconcat(states, name):
            lines, prev = ["ffconcat version 1.0"], None
            segs = []
            for t, png in states:
                rt = min(max(0.0, t - t_cap0), dur)
                if segs and abs(segs[-1][0] - rt) < 1e-3:
                    segs[-1] = (rt, png)
                else:
                    segs.append((rt, png))
            if not segs or segs[0][0] > 0:
                segs.insert(0, (0.0, "blank.png"))
            for i, (rt, png) in enumerate(segs):
                end = segs[i + 1][0] if i + 1 < len(segs) else dur + 1
                if end - rt > 0.001:
                    lines += [f"file 'overlay/{png}'", f"duration {end - rt:.3f}"]
                prev = png
            lines.append(f"file 'overlay/{prev}'")
            p = self.out / name
            p.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return p.name

        graph = [f"[0:v]fps={FPS},format=rgba[c0]"]
        cur = "c0"
        for i, b in enumerate(self.blurs[:60]):  # other apps' windows come first
            x, y, bw, bh = (max(0, v) for v in b["rect"])
            bw, bh = min(bw, w - x), min(bh, h - y)
            if bw < 4 or bh < 4:
                continue
            a, z = max(0.0, b["t0"] - t_cap0), max(0.0, b["t1"] - t_cap0)
            strong = b.get("strong")
            # blurred in full-resolution colour (yuva444p), so the radius only has to fit the box itself
            rad = max(1, min(24 if strong else 12, min(bw, bh) // 2 - 1))
            graph.append(f"[{cur}]split[s{i}a][s{i}b];[s{i}b]crop={bw}:{bh}:{x}:{y},format=yuva444p,"
                         f"boxblur={rad}:{3 if strong else 2},format=rgba[s{i}c];"
                         f"[s{i}a][s{i}c]overlay={x}:{y}:enable='between(t,{a:.3f},{z:.3f})'[b{i}]")
            cur = f"b{i}"
        graph.append(f"[1:v]format=rgba[con];[{cur}][con]overlay=0:0:eof_action=pass[cc]")
        cur = "cc"
        if self.zooms:
            dz = ZOOM_MS / 1000
            ease = lambda a: f"(0.5-0.5*cos(PI*clip((it-{a:.3f})/{dz},0,1)))"
            terms_z, terms_x, terms_y = [], [], []
            for zm in self.zooms:
                a = zm["t_in"] - t_cap0
                b = (zm["t_out"] or (t_cap0 + dur)) - t_cap0
                e = f"({ease(a)}-{ease(b)})"
                zx, zy, zw, zh = zm["rect"]
                s = min(zm["scale"], 0.9 * w / max(zw, 1), 0.9 * h / max(zh, 1))
                if s < 1.05:
                    continue
                terms_z.append(f"{s - 1:.4f}*{e}")
                terms_x.append(f"{2 * (zx + zw / 2) - w:.1f}*{e}")
                terms_y.append(f"{2 * (zy + zh / 2) - h:.1f}*{e}")
            if terms_z:
                Z = "1+" + "+".join(terms_z)
                CX = f"{w}+" + "+".join(terms_x)
                CY = f"{h}+" + "+".join(terms_y)
                graph.append(f"[{cur}]scale={2 * w}:{2 * h}:flags=lanczos,"
                             f"zoompan=z='{Z}':x='clip(({CX})-iw/zoom/2,0,iw-iw/zoom)':"
                             f"y='clip(({CY})-ih/zoom/2,0,ih-ih/zoom)':d=1:s={w}x{h}:fps={FPS}[cz]")
                cur = "cz"
        graph.append(f"[2:v]format=rgba[scr];[{cur}][scr]overlay=0:0:eof_action=pass,format=yuvj420p[v]")
        fdir = self.out / "frames"
        if fdir.exists():
            for old in fdir.glob("*.jpg"):
                old.unlink()
        fdir.mkdir(exist_ok=True)
        self.log(f"  compositing the capture ({dur:.1f}s, {len(self.blurs)} masked areas, {len(self.zooms)} zooms)")
        ffmpeg("-i", "capture.mkv", "-f", "concat", "-safe", "0", "-i", ffconcat(content, "content.ffconcat"),
               "-f", "concat", "-safe", "0", "-i", ffconcat(screen, "screen.ffconcat"),
               "-filter_complex", ";".join(graph), "-map", "[v]", "-t", f"{dur:.3f}", "-q:v", "2",
               "-start_number", "0", str(fdir / "%06d.jpg"), cwd=self.out)
        n = len(list(fdir.glob("*.jpg")))
        if not n:
            raise RuntimeError("compositing produced no frames")
        return [[round(t_cap0 + i / FPS, 4), i] for i in range(n)]


def record_desktop(sb, narr: dict, out: Path, log=print) -> tuple[dict, list, list]:
    _require_windows()
    out.mkdir(parents=True, exist_ok=True)
    log("  the desktop driver moves the real mouse and types: do not touch the machine until it finishes")
    rec = DesktopRecorder(sb, narr, out, log=log)
    try:
        timeline = rec.run()
    finally:
        if rec._guard_stop:
            rec._guard_stop.set()
        if getattr(rec, "proc", None) and rec.proc.poll() is None:
            rec.proc.kill()
    return timeline, rec.strings, rec.masked
