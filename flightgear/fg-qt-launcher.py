#!/usr/bin/env python3
"""
COSMIC FlightGear Qt Launcher  (fg-qt-launcher.py)
====================================================
One-click desktop launcher that embeds the COSMIC web UI in a native Qt
window and runs the FlightGear launcher HTTP server in-process.

• No separate server process needed — bundled here.
• Serves index.html from the same directory as this script.
• Live FlightGear status in the status bar.
• Kill FlightGear from the toolbar or on window close.

Requirements (install one):
    pip install PyQt5 PyQtWebEngine --break-system-packages
    pip install PySide6 --break-system-packages

Usage:
    python3 fg-qt-launcher.py
    python3 fg-qt-launcher.py --fgfs /path/to/fgfs
    python3 fg-qt-launcher.py --port 8765
    python3 fg-qt-launcher.py --no-kill-on-exit   # keep FG after launcher closes
    python3 fg-qt-launcher.py --url               # open in system browser instead
"""

import argparse
import http.server
import json
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

# ── directory that holds this script and index.html ───────────────────────────
LAUNCH_DIR = Path(__file__).resolve().parent

# ── Launcher server constants (kept in sync with fg-launcher-server.py) ───────
DEFAULT_PORT       = 8765
DEFAULT_FGFS       = "/home/radxa/builds/flightgear/build/src/Main/fgfs"
DEFAULT_FG_HOME    = "/home/radxa/.fgfs"
DEFAULT_FG_ROOT    = "/home/radxa/.fgfs/fgdata_2024_1"
DEFAULT_FG_SCENERY = "/home/radxa/.fgfs/TerraSync:/home/radxa/.fgfs/fgdata_2024_1/Scenery"
FG_VERSION         = "2024.1.7"
MAX_LAUNCH_ARGS = 40
ALLOWED_ARG_PREFIXES = (
    "--fg-root=", "--fg-aircraft=", "--airport=", "--runway=",
    "--lat=", "--lon=", "--heading=", "--altitude=", "--vc=",
    "--aircraft=", "--timeofday=", "--prop:", "--enable-",
    "--disable-", "--geometry=", "--bpp=", "--fov=", "--aspect-ratio=",
    "--callsign=", "--season=", "--wind=", "--turbulence=",
    "--visibility=", "--clouds=", "--cloud-coverage=",
    "--multiplay=", "--fg-scenery=", "--terrasync-dir=",
    "--log-level=", "--log-class=", "--fdm=", "--aero=",
    "--model-hz=", "--speed=", "--trim", "--notrim",
    "--start-date-lat=", "--end-date-lat=",
    "--in-air", "--on-ground",
    "--garmin", "--nav1=", "--nav2=", "--adf=", "--dme=", "--com1=", "--com2=",
)

# ── Global server state (shared across handler instances) ─────────────────────
_fgfs_path     = DEFAULT_FGFS
_fg_home       = DEFAULT_FG_HOME
_fg_root       = DEFAULT_FG_ROOT
_fg_scenery    = DEFAULT_FG_SCENERY
_active_proc   = None
_proc_lock     = threading.Lock()
_server_port   = DEFAULT_PORT


def _validate_args(args_list):
    """Return (ok, reason). Blocks shell injection and non-fgfs flags."""
    if len(args_list) > MAX_LAUNCH_ARGS:
        return False, f"Too many arguments ({len(args_list)} > {MAX_LAUNCH_ARGS})"
    for arg in args_list:
        bad = set(';&|`$(){}[]<>\n\r\t\\')
        if any(c in arg for c in bad):
            return False, f"Disallowed character in argument: {arg!r}"
        if not any(arg.startswith(p) for p in ALLOWED_ARG_PREFIXES):
            return False, f"Argument not in allowlist: {arg!r}"
    return True, ""


def _kill_fg():
    """Terminate active FlightGear process. Returns status string."""
    global _active_proc
    with _proc_lock:
        if _active_proc is not None:
            pid = _active_proc.pid
            if _active_proc.poll() is None:
                try:
                    os.killpg(os.getpgid(pid), signal.SIGTERM)
                    _active_proc.wait(timeout=3)
                except Exception:
                    try:
                        _active_proc.kill()
                    except Exception:
                        pass
            _active_proc = None
            return f"killed pid {pid}"
    return "no active process"


class _Handler(http.server.BaseHTTPRequestHandler):
    """HTTP handler: serves index.html + the FlightGear launcher REST API."""

    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S")
        # Suppress noisy 200 GETs for status polling; keep errors visible
        code = args[1] if len(args) > 1 else ""
        if code not in ("200",):
            print(f"[{ts}] {fmt % args}", flush=True)

    # ── CORS helpers ──────────────────────────────────────────────────────────
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    # ── OPTIONS pre-flight ────────────────────────────────────────────────────
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    # ── GET ───────────────────────────────────────────────────────────────────
    def do_GET(self):
        global _active_proc
        path = urlparse(self.path).path

        if path in ("/", "/index.html"):
            self._serve_index()

        elif path in ("/status",):
            active = _active_proc is not None and _active_proc.poll() is None
            self._json(200, {
                "status":      "running",
                "fgfs":        _fgfs_path,
                "fg_version":  FG_VERSION,
                "fgfs_exists": os.path.isfile(_fgfs_path),
                "active":      active,
                "pid":         _active_proc.pid if active else None,
                "fg_home":     _fg_home,
                "fg_root":     _fg_root,
                "fg_scenery":  _fg_scenery,
            })

        elif path == "/kill":
            msg = _kill_fg()
            self._json(200, {"killed": msg})

        else:
            self.send_response(404)
            self.end_headers()

    # ── POST ──────────────────────────────────────────────────────────────────
    def do_POST(self):
        global _active_proc
        path = urlparse(self.path).path

        if path == "/launch":
            length = int(self.headers.get("Content-Length", 0))
            raw    = self.rfile.read(length)
            try:
                data = json.loads(raw)
            except Exception as e:
                self._json(400, {"error": f"Bad JSON: {e}"}); return

            args_list = data.get("args", [])
            if not isinstance(args_list, list):
                self._json(400, {"error": "args must be a list"}); return

            ok, reason = _validate_args(args_list)
            if not ok:
                self._json(400, {"error": f"Validation failed: {reason}"}); return

            if not os.path.isfile(_fgfs_path):
                self._json(500, {"error": f"fgfs not found at {_fgfs_path}"}); return

            cmd = [_fgfs_path] + args_list
            print(f"  LAUNCH: {' '.join(shlex.quote(a) for a in cmd)}", flush=True)

            _kill_fg()

            fg_env = {
                **os.environ,
                "FG_HOME":    _fg_home,
                "FG_ROOT":    _fg_root,
                "FG_SCENERY": _fg_scenery,
            }

            with _proc_lock:
                try:
                    _active_proc = subprocess.Popen(
                        cmd,
                        env=fg_env,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    pid = _active_proc.pid
                except Exception as e:
                    self._json(500, {"error": f"Failed to start fgfs: {e}"}); return

            self._json(200, {"launched": True, "pid": pid, "cmd": cmd})

        elif path == "/kill":
            msg = _kill_fg()
            self._json(200, {"killed": msg})

        else:
            self.send_response(404)
            self.end_headers()

    # ── Serve index.html with port-patched LAUNCHER constant ─────────────────
    def _serve_index(self):
        html_path = LAUNCH_DIR / "index.html"
        if not html_path.is_file():
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"index.html not found")
            return

        html = html_path.read_text("utf-8")
        # Patch the hardcoded port so the page talks to wherever we're running
        html = html.replace(
            "const LAUNCHER = 'http://localhost:8765'",
            f"const LAUNCHER = 'http://localhost:{_server_port}'",
        )
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)


# ── Background HTTP server thread ─────────────────────────────────────────────
class _ServerThread(threading.Thread):
    def __init__(self, port):
        super().__init__(daemon=True, name="FGLauncherHTTP")
        self.port = port
        self._server = None
        self.ready   = threading.Event()

    def run(self):
        try:
            self._server = http.server.ThreadingHTTPServer(
                ("127.0.0.1", self.port), _Handler
            )
            self.ready.set()
            self._server.serve_forever()
        except Exception as exc:
            print(f"[server] ERROR: {exc}", file=sys.stderr, flush=True)
            self.ready.set()

    def stop(self):
        if self._server:
            self._server.shutdown()


# ── Status poller: daemon thread → calls callback on Qt main thread ───────────
class _StatusPoller(threading.Thread):
    def __init__(self, port, callback):
        super().__init__(daemon=True, name="FGStatusPoller")
        self.port      = port
        self.callback  = callback   # called with dict on Qt main thread
        self._stop_evt = threading.Event()

    def run(self):
        while not self._stop_evt.wait(2.0):
            try:
                with urllib.request.urlopen(
                    f"http://localhost:{self.port}/status", timeout=2
                ) as resp:
                    data = json.loads(resp.read())
            except Exception:
                data = {}
            # Schedule on Qt main thread
            try:
                from _qt import QTimer
                QTimer.singleShot(0, lambda d=data: self.callback(d))
            except Exception:
                pass  # Qt not ready yet

    def stop(self):
        self._stop_evt.set()


# ─────────────────────────────────────────────────────────────────────────────
#  Qt UI
# ─────────────────────────────────────────────────────────────────────────────

def _qt_imports():
    """Import Qt classes; return (QTimer, QUrl, QApplication, QMainWindow,
    QAction, QLabel, QStatusBar, QMessageBox, QWebEngineView_or_None, backend_name)."""

    # Try PyQt5 first, then PySide6
    for backend in ("PyQt5", "PySide6"):
        try:
            if backend == "PyQt5":
                from PyQt5.QtCore    import QTimer, QUrl
                from PyQt5.QtWidgets import (QApplication, QMainWindow, QAction,
                                              QLabel, QStatusBar, QMessageBox,
                                              QSizePolicy, QToolBar)
                try:
                    from PyQt5.QtWebEngineWidgets import QWebEngineView
                    from PyQt5.QtWebEngineCore    import QWebEngineSettings
                except ImportError:
                    QWebEngineView  = None
                    QWebEngineSettings = None
            else:
                from PySide6.QtCore    import QTimer, QUrl
                from PySide6.QtGui     import QAction
                from PySide6.QtWidgets import (QApplication, QMainWindow,
                                               QLabel, QStatusBar, QMessageBox,
                                               QSizePolicy, QToolBar)
                try:
                    from PySide6.QtWebEngineWidgets import QWebEngineView
                    from PySide6.QtWebEngineCore    import QWebEngineSettings
                except ImportError:
                    QWebEngineView  = None
                    QWebEngineSettings = None

            return (QTimer, QUrl, QApplication, QMainWindow, QAction,
                    QLabel, QStatusBar, QMessageBox, QSizePolicy, QToolBar,
                    QWebEngineView, QWebEngineSettings, backend)
        except ImportError:
            continue

    return None


def _run_qt(port, kill_on_exit):
    """Launch the Qt application window."""
    qt = _qt_imports()
    if qt is None:
        print(
            "ERROR: Qt not found.\n"
            "Install with one of:\n"
            "  pip install PyQt5 PyQtWebEngine --break-system-packages\n"
            "  pip install PySide6 --break-system-packages\n\n"
            f"Then open:  http://localhost:{port}/  in a browser after starting\n"
            "  python3 fg-launcher-server.py",
            file=sys.stderr,
        )
        return 1

    (QTimer, QUrl, QApplication, QMainWindow, QAction,
     QLabel, QStatusBar, QMessageBox, QSizePolicy, QToolBar,
     QWebEngineView, QWebEngineSettings, backend) = qt

    # Make QTimer importable by _StatusPoller (hack-free alternative: use signals)
    import sys as _sys
    _sys.modules["_qt"] = type(_sys)("_qt")
    _sys.modules["_qt"].QTimer = QTimer

    # Sandbox flag for root / some CI environments
    if os.geteuid() == 0:
        os.environ.setdefault(
            "QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox"
        )

    app = QApplication(sys.argv)
    app.setApplicationName("COSMIC FlightGear Launcher")
    app.setApplicationVersion(FG_VERSION)

    # ── Main window ───────────────────────────────────────────────────────────
    win = QMainWindow()
    win.setWindowTitle(f"COSMIC FlightGear Launcher  ·  {FG_VERSION}")
    win.resize(1400, 900)

    # ── Tool bar ──────────────────────────────────────────────────────────────
    tb = QToolBar("Controls")
    tb.setMovable(False)
    win.addToolBar(tb)

    kill_action = QAction("⏹  Kill FlightGear", win)
    kill_action.setToolTip("Terminate the running FlightGear process")
    kill_action.setEnabled(False)
    tb.addAction(kill_action)

    tb.addSeparator()

    reload_action = QAction("⟳  Reload", win)
    reload_action.setToolTip("Reload the launcher page")
    tb.addAction(reload_action)

    tb.addSeparator()

    about_action = QAction("ⓘ  About", win)
    tb.addAction(about_action)

    # ── Status bar ────────────────────────────────────────────────────────────
    sb = QStatusBar()
    win.setStatusBar(sb)

    srv_label = QLabel(f"  Server: ✓ localhost:{port}  ")
    srv_label.setStyleSheet("color: #4c8; font-family: monospace;")
    sb.addWidget(srv_label)

    sep = QLabel("|")
    sep.setStyleSheet("color: #555;")
    sb.addWidget(sep)

    fg_label = QLabel("  FlightGear: Not running  ")
    fg_label.setStyleSheet("color: #888; font-family: monospace;")
    sb.addWidget(fg_label)

    # ── Central widget: web view or fallback ──────────────────────────────────
    url_str = f"http://localhost:{port}/"

    if QWebEngineView is not None:
        view = QWebEngineView()
        if QWebEngineSettings is not None:
            # Enable local storage, JS (defaults, but be explicit)
            try:
                page_settings = view.settings()
                # PyQt5 / PySide6 attr names vary; guard each
                for attr_name in (
                    "LocalContentCanAccessRemoteUrls",
                    "AllowRunningInsecureContent",
                ):
                    try:
                        attr = getattr(QWebEngineSettings.WebAttribute,
                                       attr_name, None) or \
                               getattr(QWebEngineSettings, attr_name, None)
                        if attr is not None:
                            page_settings.setAttribute(attr, True)
                    except Exception:
                        pass
            except Exception:
                pass

        view.load(QUrl(url_str))
        win.setCentralWidget(view)

        def _reload():
            view.reload()

    else:
        # No WebEngine — show fallback with instructions
        from PyQt5.QtWidgets import QWidget, QVBoxLayout
        fallback = QWidget()
        layout   = QVBoxLayout(fallback)
        msg = QLabel(
            f"<h2>QtWebEngine not installed</h2>"
            f"<p>Install it to use the embedded launcher:</p>"
            f"<pre>  pip install PyQt5 PyQtWebEngine --break-system-packages<br>"
            f"  # or: pip install PySide6 --break-system-packages</pre>"
            f"<p>The launcher server is running at:<br>"
            f"<b><a href='{url_str}'>{url_str}</a></b></p>"
            f"<p>Open that link in any browser.</p>"
        )
        msg.setOpenExternalLinks(True)
        msg.setWordWrap(True)
        layout.addStretch()
        layout.addWidget(msg)
        layout.addStretch()
        win.setCentralWidget(fallback)

        def _reload():
            pass  # nothing to reload

    # ── Status update callback (called from _StatusPoller on main thread) ─────
    def _on_status(data):
        active = data.get("active", False)
        pid    = data.get("pid")
        exists = data.get("fgfs_exists", False)

        if active:
            fg_label.setText(f"  FlightGear: ● Running  (PID {pid})  ")
            fg_label.setStyleSheet("color: #4c8; font-family: monospace;")
            kill_action.setEnabled(True)
        else:
            fg_label.setText("  FlightGear: ○ Not running  ")
            fg_label.setStyleSheet("color: #888; font-family: monospace;")
            kill_action.setEnabled(False)

        if not exists and data:
            srv_label.setText(f"  Server: ✓  ⚠ fgfs not found  ")
            srv_label.setStyleSheet("color: #f80; font-family: monospace;")
        elif data:
            srv_label.setText(f"  Server: ✓ localhost:{port}  ")
            srv_label.setStyleSheet("color: #4c8; font-family: monospace;")
        else:
            srv_label.setText(f"  Server: ✗ localhost:{port}  ")
            srv_label.setStyleSheet("color: #f44; font-family: monospace;")

    # ── Wire up actions ───────────────────────────────────────────────────────
    def _do_kill():
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"http://localhost:{port}/kill", method="POST"
                ),
                timeout=3,
            )
        except Exception:
            _kill_fg()  # direct kill if HTTP fails

    def _do_about():
        QMessageBox.information(
            win, "About COSMIC FlightGear Launcher",
            f"<b>COSMIC FlightGear Launcher</b><br>"
            f"FlightGear {FG_VERSION}<br><br>"
            f"Qt backend: {backend}<br>"
            f"Server port: {port}<br>"
            f"fgfs: {_fgfs_path}<br><br>"
            f"<a href='https://www.flightgear.org'>flightgear.org</a>",
        )

    kill_action.triggered.connect(_do_kill)
    reload_action.triggered.connect(_reload)
    about_action.triggered.connect(_do_about)

    # ── Close handler ─────────────────────────────────────────────────────────
    def _close_event(event):
        if kill_on_exit:
            active = _active_proc is not None and _active_proc.poll() is None
            if active:
                reply = QMessageBox.question(
                    win,
                    "FlightGear is running",
                    "FlightGear is still running. Kill it before closing?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    if hasattr(QMessageBox, "StandardButton")
                    else QMessageBox.Yes | QMessageBox.No,
                )
                yes = (
                    reply == QMessageBox.StandardButton.Yes
                    if hasattr(QMessageBox, "StandardButton")
                    else reply == QMessageBox.Yes
                )
                if yes:
                    _kill_fg()
        event.accept()

    win.closeEvent = _close_event

    # ── Start status poller ───────────────────────────────────────────────────
    poller = _StatusPoller(port, _on_status)
    poller.start()

    # ── Show window & run ─────────────────────────────────────────────────────
    win.show()
    ret = app.exec() if hasattr(app, "exec") else app.exec_()

    poller.stop()
    return ret


# ─────────────────────────────────────────────────────────────────────────────
#  Open-in-browser mode (no Qt)
# ─────────────────────────────────────────────────────────────────────────────

def _open_browser(port):
    import webbrowser
    url = f"http://localhost:{port}/"
    print(f"Opening {url} in system browser…")
    webbrowser.open(url)


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global _fgfs_path, _fg_home, _fg_root, _fg_scenery, _server_port

    parser = argparse.ArgumentParser(
        description="COSMIC FlightGear Qt Launcher",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--port",       type=int, default=DEFAULT_PORT,
                        help=f"HTTP port (default {DEFAULT_PORT})")
    parser.add_argument("--fgfs",       default=DEFAULT_FGFS,
                        help=f"Path to fgfs binary (default: {DEFAULT_FGFS})")
    parser.add_argument("--fg-home",    default=DEFAULT_FG_HOME,
                        help=f"FG_HOME env var (default: {DEFAULT_FG_HOME})")
    parser.add_argument("--fg-root",    default=DEFAULT_FG_ROOT,
                        help=f"FG_ROOT env var (default: {DEFAULT_FG_ROOT})")
    parser.add_argument("--fg-scenery", default=DEFAULT_FG_SCENERY,
                        help=f"FG_SCENERY env var (default: {DEFAULT_FG_SCENERY})")
    parser.add_argument("--no-kill-on-exit", action="store_true",
                        help="Leave FlightGear running when the launcher closes")
    parser.add_argument("--url", action="store_true",
                        help="Print server URL and open in system browser (no Qt)")
    args = parser.parse_args()

    _fgfs_path   = args.fgfs
    _fg_home     = args.fg_home
    _fg_root     = args.fg_root
    _fg_scenery  = args.fg_scenery
    _server_port = args.port

    # Check index.html exists
    if not (LAUNCH_DIR / "index.html").is_file():
        sys.exit(
            f"ERROR: index.html not found in {LAUNCH_DIR}\n"
            "Run this script from the flightgear/ directory or place it alongside index.html."
        )

    # Warn if fgfs missing
    if not os.path.isfile(_fgfs_path):
        print(f"WARNING: fgfs not found at {_fgfs_path}  (set --fgfs path)", flush=True)

    # Start HTTP server
    srv = _ServerThread(args.port)
    srv.start()
    if not srv.ready.wait(timeout=5):
        sys.exit("ERROR: HTTP server failed to start within 5 seconds.")
    print(
        f"\n  COSMIC FlightGear Launcher\n"
        f"  Server     :  http://localhost:{args.port}/\n"
        f"  fgfs       :  {_fgfs_path}\n"
        f"  FG_HOME    :  {_fg_home}\n"
        f"  FG_ROOT    :  {_fg_root}\n"
        f"  FG_SCENERY :  {_fg_scenery}\n"
        f"  Version    :  FlightGear {FG_VERSION}\n",
        flush=True,
    )

    if args.url:
        _open_browser(args.port)
        print("Press Ctrl+C to stop the server.", flush=True)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down.")
        finally:
            _kill_fg()
            srv.stop()
        return 0

    # Launch Qt app
    ret = _run_qt(args.port, kill_on_exit=not args.no_kill_on_exit)

    # Clean up
    _kill_fg()
    srv.stop()
    sys.exit(ret)


if __name__ == "__main__":
    main()
