#!/usr/bin/env python3
"""
COSMIC FlightGear Launcher Server
Tiny HTTP server that receives POST /launch from the browser page
and executes fgfs commands locally. Run this before using "Launch" buttons.

Usage:
    python3 fg-launcher-server.py
    python3 fg-launcher-server.py --port 8765
    python3 fg-launcher-server.py --fgfs /usr/local/bin/fgfs

Opens http://localhost:8765/status to check it's running.
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
from urllib.parse import urlparse

DEFAULT_PORT = 8765
DEFAULT_FGFS = "/usr/local/bin/fgfs"
CORS_ORIGIN = "*"          # GitHub Pages can be any origin; restrict here if desired
MAX_LAUNCH_ARGS = 40       # Safety limit on number of args
ALLOWED_ARG_PREFIXES = (   # Whitelist: only fgfs flags
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

fgfs_path = DEFAULT_FGFS
active_process = None
process_lock = threading.Lock()


def validate_args(args_list):
    """Return (ok, reason). Blocks shell injection and non-fgfs flags."""
    if len(args_list) > MAX_LAUNCH_ARGS:
        return False, f"Too many arguments ({len(args_list)} > {MAX_LAUNCH_ARGS})"
    for arg in args_list:
        # No shell metacharacters
        bad = set(';&|`$(){}[]<>\n\r\t\\')
        if any(c in arg for c in bad):
            return False, f"Disallowed character in argument: {arg!r}"
        # Must start with an allowed prefix
        if not any(arg.startswith(p) for p in ALLOWED_ARG_PREFIXES):
            return False, f"Argument not in allowlist: {arg!r}"
    return True, ""


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        ts = time.strftime("%H:%M:%S")
        print(f"[{ts}] {fmt % args}")

    def send_cors(self):
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors()
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/status"):
            body = json.dumps({
                "status": "running",
                "fgfs": fgfs_path,
                "fgfs_exists": os.path.isfile(fgfs_path),
                "active": active_process is not None and active_process.poll() is None,
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)
        elif path == "/kill":
            msg = self._kill_fg()
            body = json.dumps({"killed": msg}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        global active_process
        path = urlparse(self.path).path

        if path == "/launch":
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw)
            except Exception as e:
                self._error(400, f"Bad JSON: {e}")
                return

            args_list = data.get("args", [])
            if not isinstance(args_list, list):
                self._error(400, "args must be a list")
                return

            ok, reason = validate_args(args_list)
            if not ok:
                self._error(400, f"Validation failed: {reason}")
                return

            if not os.path.isfile(fgfs_path):
                self._error(500, f"fgfs not found at {fgfs_path}")
                return

            cmd = [fgfs_path] + args_list
            print(f"  LAUNCH: {' '.join(shlex.quote(a) for a in cmd)}")

            # Kill any existing FG instance
            self._kill_fg()

            with process_lock:
                try:
                    active_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
                    pid = active_process.pid
                except Exception as e:
                    self._error(500, f"Failed to start fgfs: {e}")
                    return

            body = json.dumps({"launched": True, "pid": pid, "cmd": cmd}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)

        elif path == "/kill":
            msg = self._kill_fg()
            body = json.dumps({"killed": msg}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_cors()
            self.end_headers()
            self.wfile.write(body)

        else:
            self.send_response(404)
            self.end_headers()

    def _kill_fg(self):
        global active_process
        with process_lock:
            if active_process is not None:
                pid = active_process.pid
                if active_process.poll() is None:
                    try:
                        os.killpg(os.getpgid(pid), signal.SIGTERM)
                        active_process.wait(timeout=3)
                    except Exception:
                        try:
                            active_process.kill()
                        except Exception:
                            pass
                active_process = None
                return f"killed pid {pid}"
        return "no active process"

    def _error(self, code, msg):
        body = json.dumps({"error": msg}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_cors()
        self.end_headers()
        self.wfile.write(body)


def main():
    global fgfs_path
    parser = argparse.ArgumentParser(description="COSMIC FlightGear Launcher Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--fgfs", default=DEFAULT_FGFS)
    args = parser.parse_args()
    fgfs_path = args.fgfs

    if not os.path.isfile(fgfs_path):
        print(f"WARNING: fgfs not found at {fgfs_path} — set --fgfs path")

    server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"COSMIC Launcher Server  →  http://localhost:{args.port}/status")
    print(f"fgfs binary             :  {fgfs_path}")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
