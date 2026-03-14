"""
ui.py  —  JARVIS Web UI (pywebview)
Drop-in replacement for the original Tkinter ui.py.
Public API is identical so main.py needs zero changes.
"""

import os, json, time, base64, threading, sys
from pathlib import Path

import webview


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = get_base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"
HTML_FILE  = BASE_DIR / "ui_assets" / "index.html"

SYSTEM_NAME = "J.A.R.V.I.S"
MODEL_BADGE = "MARK XXX"


# ─────────────────────────────────────────────────────────────────────────────
# JS ↔ Python bridge (exposed to JavaScript as window.pywebview.api)
# ─────────────────────────────────────────────────────────────────────────────
class _PyAPI:
    def __init__(self, ui: "JarvisUI"):
        self._ui = ui

    def save_api_key(self, key: str) -> bool:
        key = (key or "").strip()
        if not key:
            return False
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(API_FILE, "w", encoding="utf-8") as f:
            json.dump({"gemini_api_key": key}, f, indent=4)
        self._ui._api_key_ready = True
        # tell the page to close the modal and go online
        self._ui._js("J.hideApiSetup()")
        self._ui._js("J.setStatus('ONLINE')")
        self._ui._js("J.addLog('SYS: Systems initialised. JARVIS online.')")
        return True


# ─────────────────────────────────────────────────────────────────────────────
# Compatibility shim — lets main.py call ui.root.mainloop() unchanged
# ─────────────────────────────────────────────────────────────────────────────
class _RootCompat:
    def __init__(self, ui: "JarvisUI"):
        self._ui = ui

    def mainloop(self):
        webview.start(debug=False, private_mode=False)

    def protocol(self, name, func):
        pass  # pywebview handles window close via OS chrome


# ─────────────────────────────────────────────────────────────────────────────
# JarvisUI  — same public surface as the old Tkinter version
# ─────────────────────────────────────────────────────────────────────────────
class JarvisUI:

    def __init__(self, face_path, size=None):
        self.speaking    = False
        self.status_text = "INITIALISING"

        self._api_key_ready  = self._api_keys_exist()
        self._face_b64       = self._load_face_b64(face_path)
        self._window         = None
        self._dom_ready      = threading.Event()
        self._pre_load_queue = []   # messages queued before DOM is ready

        api = _PyAPI(self)
        html = self._build_html()

        self._window = webview.create_window(
            title            = f"{SYSTEM_NAME} — {MODEL_BADGE}",
            html             = html,
            js_api           = api,
            width            = 984,
            height           = 816,
            resizable        = False,
            background_color = "#000000",
            min_size         = (984, 816),
        )
        self._window.events.loaded += self._on_loaded
        self.root = _RootCompat(self)

    # ── internal helpers ────────────────────────────────────────────────────

    def _js(self, code: str):
        """Send JS to the page (thread-safe)."""
        if self._window:
            try:
                self._window.evaluate_js(code)
            except Exception:
                pass

    def _on_loaded(self):
        """Fires once the DOM + scripts are ready."""
        self._dom_ready.set()

        if self._face_b64:
            self._js(f"J.setFace('data:image/png;base64,{self._face_b64}')")
        else:
            self._js("J.showOrb()")

        if not self._api_key_ready:
            self._js("J.showApiSetup()")
        else:
            self._js("J.setStatus('ONLINE')")
            self._js("J.addLog('SYS: JARVIS ready.')")

        # flush anything queued before load
        for msg in self._pre_load_queue:
            self._js(msg)
        self._pre_load_queue.clear()

    def _escape(self, text: str) -> str:
        return (text
                .replace("\\", "\\\\")
                .replace("'", "\\'")
                .replace("\n", "\\n")
                .replace("\r", ""))

    def _build_html(self) -> str:
        if HTML_FILE.exists():
            return HTML_FILE.read_text(encoding="utf-8")
        return ("<html><body style='background:#000;color:#0ff;font-family:monospace'>"
                "<p>ERROR: ui_assets/index.html not found.</p></body></html>")

    def _load_face_b64(self, face_path) -> str:
        try:
            p = Path(face_path)
            if not p.is_absolute():
                p = BASE_DIR / face_path
            return base64.b64encode(p.read_bytes()).decode("utf-8")
        except Exception:
            return ""

    @staticmethod
    def _api_keys_exist() -> bool:
        return API_FILE.exists()

    # ── public API (called by main.py + action modules) ─────────────────────

    def write_log(self, text: str):
        escaped = self._escape(text)
        cmd = f"J.addLog('{escaped}')"
        if not self._dom_ready.is_set():
            self._pre_load_queue.append(cmd)
        else:
            self._js(cmd)

        tl = text.lower()
        if tl.startswith("you:"):
            self.status_text = "PROCESSING"
        elif tl.startswith("jarvis:"):
            self.status_text = "RESPONDING"

    def start_speaking(self):
        self.speaking    = True
        self.status_text = "SPEAKING"
        if self._dom_ready.is_set():
            self._js("J.setSpeaking(true)")

    def stop_speaking(self):
        self.speaking    = False
        self.status_text = "ONLINE"
        if self._dom_ready.is_set():
            self._js("J.setSpeaking(false)")

    def set_sleeping(self, sleeping: bool):
        """Dim / brighten the HUD based on wake word state."""
        if self._dom_ready.is_set():
            val = "true" if sleeping else "false"
            self._js(f"J.setSleeping({val})")

    def wait_for_api_key(self):
        """Block the JARVIS worker thread until the API key is saved."""
        while not self._api_key_ready:
            time.sleep(0.1)