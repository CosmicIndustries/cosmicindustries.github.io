#!/usr/bin/env python3
"""
fftest2026 — Modern Linux Force Feedback Test Utility
Designed for ARM64 / Rock 5B+ with hid-pidff kernel (6.1.84-8-rk2410-pidff-6)

Improvements over fftest (joystick 1:1.8.1-1, ~2014):
  • Auto-detects FF-capable /dev/input/event* devices (parallel scan)
  • Memoized capability queries (cached_property + lru_cache — zero re-read overhead)
  • Parallelised effect upload/playback via ThreadPoolExecutor
  • Complete effect suite: RUMBLE CONSTANT SINE SQUARE TRIANGLE SAW_UP SAW_DOWN SPRING DAMPER RAMP
  • IOCTL-correct n_effects query (EVIOCGEFFECTS) so 0-effect devices are caught up front
  • Interactive picker + batch smoke-test + JSON report
  • No extra deps: stdlib + python3-evdev only

Usage:
  ./fftest2026.py                        # auto-detect FF device, interactive
  ./fftest2026.py /dev/input/event4      # target specific device
  ./fftest2026.py --list                 # list all FF-capable devices and exit
  ./fftest2026.py --batch                # smoke-test all effects, non-interactive
  ./fftest2026.py --batch --seq          # sequential (safe for n_effects=1 devices)
  ./fftest2026.py --json                 # JSON report to stdout (CI/scripting)
  ./fftest2026.py --gain 60              # set device gain before testing (default: 75)
"""

import sys, os, time, json, argparse, fcntl, struct, threading
from functools import cached_property, lru_cache
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import evdev
    from evdev import ecodes as ec
    import evdev.ff as ff
except ImportError:
    sys.exit("pip install evdev --break-system-packages")

# ─── ANSI colour helpers ──────────────────────────────────────────────────────
R   = "\033[0m"
B   = "\033[1m"       # bold
DIM = "\033[2m"
GRN = "\033[92m"
YLW = "\033[93m"
RED = "\033[91m"
BLU = "\033[94m"
CYN = "\033[96m"

def ok(s):  return f"{GRN}✓{R} {s}"
def err(s): return f"{RED}✗{R} {s}"
def inf(s): return f"{BLU}·{R} {s}"
def wrn(s): return f"{YLW}⚠{R} {s}"
def hdr(s): return f"\n{CYN}{B}{s}{R}"

# ─── IOCTL: EVIOCGEFFECTS = _IOR('E', 0x84, int) = 0x80044584 ───────────────
# dir=READ(2)<<30 | size=4<<16 | type='E'(0x45)<<8 | nr=0x84
EVIOCGEFFECTS = (2 << 30) | (4 << 16) | (0x45 << 8) | 0x84

def ioctl_ff_count(fd: int) -> int:
    """Query max simultaneous FF effects via EVIOCGEFFECTS ioctl."""
    buf = bytearray(4)
    try:
        fcntl.ioctl(fd, EVIOCGEFFECTS, buf, True)
        return struct.unpack('i', bytes(buf))[0]
    except OSError:
        return 0

# ─── FFDevice: evdev wrapper with memoized FF introspection ──────────────────
class FFDevice:
    """
    Wraps evdev.InputDevice.
    All capability queries are cached_property — the kernel is only asked once
    per device instance, even across repeated calls.
    """

    def __init__(self, path: str):
        self.path = path
        self._dev = evdev.InputDevice(path)

    @cached_property
    def name(self) -> str:
        return self._dev.name

    @cached_property
    def _raw_caps(self) -> dict:
        """Raw capability dict — memoized so the ioctl fires once."""
        return self._dev.capabilities()

    @cached_property
    def ff_codes(self) -> set:
        """Set of supported EV_FF codes (integers). Memoized."""
        raw = self._raw_caps.get(ec.EV_FF, [])
        out = set()
        for c in raw:
            if hasattr(c, 'code'):
                out.add(c.code)
            elif hasattr(c, 'value'):
                out.add(c.value)
            else:
                try:
                    out.add(int(c))
                except (TypeError, ValueError):
                    pass
        return out

    @cached_property
    def n_effects(self) -> int:
        """Max simultaneous effects (EVIOCGEFFECTS). Memoized."""
        return ioctl_ff_count(self._dev.fd)

    @cached_property
    def is_ff(self) -> bool:
        """True if the device has any EV_FF capability."""
        return ec.EV_FF in self._raw_caps and bool(self.ff_codes)

    def supports(self, code: int) -> bool:
        return code in self.ff_codes

    def gain(self, pct: int):
        """Set device gain 0–100. No-op if FF_GAIN not supported."""
        if ec.FF_GAIN in self.ff_codes:
            self._dev.write(ec.EV_FF, ec.FF_GAIN, int(pct / 100 * 0xFFFF))

    def autocenter(self, pct: int):
        """Set autocenter 0–100."""
        if ec.FF_AUTOCENTER in self.ff_codes:
            self._dev.write(ec.EV_FF, ec.FF_AUTOCENTER, int(pct / 100 * 0xFFFF))

    def play_effect(self, effect, duration_ms: int) -> tuple:
        """Upload, play, wait duration_ms, stop, erase. Returns (ok, msg)."""
        try:
            eid = self._dev.upload_effect(effect)
            self._dev.write(ec.EV_FF, eid, 1)
            time.sleep(duration_ms / 1000)
            self._dev.write(ec.EV_FF, eid, 0)
            self._dev.erase_effect(eid)
            return True, ""
        except OSError as ex:
            return False, str(ex)

    def __repr__(self):
        return f"FFDevice({self.path!r}  {self.name!r}  n_effects={self.n_effects})"

# ─── Effect factories ─────────────────────────────────────────────────────────

def make_rumble(strong=0x8000, weak=0x4000, ms=600):
    return ff.Effect(ec.FF_RUMBLE, -1, 0,
        ff.Trigger(0, 0), ff.Replay(ms, 0),
        ff.EffectType(ff_rumble_effect=ff.Rumble(
            strong_magnitude=strong, weak_magnitude=weak)))

def make_constant(level=0x5000, ms=500, direction=0):
    return ff.Effect(ec.FF_CONSTANT, -1, direction,
        ff.Trigger(0, 0), ff.Replay(ms, 0),
        ff.EffectType(ff_constant_effect=ff.Constant(
            level=level,
            envelope=ff.Envelope(attack_length=0, attack_level=0,
                                  fade_length=0, fade_level=0))))

def make_periodic(wave, mag=0x4000, period_ms=150, ms=800):
    return ff.Effect(ec.FF_PERIODIC, -1, 0,
        ff.Trigger(0, 0), ff.Replay(ms, 0),
        ff.EffectType(ff_periodic_effect=ff.Periodic(
            waveform=wave, period=period_ms, magnitude=mag,
            offset=0, phase=0,
            envelope=ff.Envelope(0, 0, 0, 0))))

def _cond_pair(coeff=0x2000, sat=0x7fff):
    c = ff.Condition(right_saturation=sat, left_saturation=sat,
                     right_coeff=coeff, left_coeff=coeff,
                     deadband=0, center=0)
    return (ff.Condition * 2)(c, c)

def make_spring(stiff=0x2000, sat=0x7fff, ms=1500):
    return ff.Effect(ec.FF_SPRING, -1, 0,
        ff.Trigger(0, 0), ff.Replay(ms, 0),
        ff.EffectType(ff_condition_effect=_cond_pair(stiff, sat)))

def make_damper(coeff=0x2000, sat=0x7fff, ms=1500):
    return ff.Effect(ec.FF_DAMPER, -1, 0,
        ff.Trigger(0, 0), ff.Replay(ms, 0),
        ff.EffectType(ff_condition_effect=_cond_pair(coeff, sat)))

def make_ramp(start=0x5000, end=-0x5000, ms=1000):
    return ff.Effect(ec.FF_RAMP, -1, 0,
        ff.Trigger(0, 0), ff.Replay(ms, 0),
        ff.EffectType(ff_ramp_effect=ff.Ramp(
            start_level=start, end_level=end,
            envelope=ff.Envelope(0, 0, 0, 0))))

# ─── Test suite definition ────────────────────────────────────────────────────
# (name, required_code, factory_fn, play_duration_ms)
# required_code: the EV_FF code that must be in ff_codes to attempt this test
SUITE = [
    ("rumble",     ec.FF_RUMBLE,   lambda: make_rumble(),                    600),
    ("constant",   ec.FF_CONSTANT, lambda: make_constant(),                  500),
    ("sine",       ec.FF_PERIODIC, lambda: make_periodic(ec.FF_SINE),        800),
    ("square",     ec.FF_PERIODIC, lambda: make_periodic(ec.FF_SQUARE),      800),
    ("triangle",   ec.FF_PERIODIC, lambda: make_periodic(ec.FF_TRIANGLE),    800),
    ("saw_up",     ec.FF_PERIODIC, lambda: make_periodic(ec.FF_SAW_UP),      800),
    ("saw_down",   ec.FF_PERIODIC, lambda: make_periodic(ec.FF_SAW_DOWN),    800),
    ("spring",     ec.FF_SPRING,   lambda: make_spring(),                   1500),
    ("damper",     ec.FF_DAMPER,   lambda: make_damper(),                   1500),
    ("ramp",       ec.FF_RAMP,     lambda: make_ramp(),                     1000),
]

def _run_one(dev: FFDevice, name: str, code: int, factory, dur: int) -> dict:
    if not dev.supports(code):
        return dict(name=name, status="skip", msg="not in ff_codes")
    ok_flag, msg = dev.play_effect(factory(), dur)
    return dict(name=name, status="ok" if ok_flag else "fail", msg=msg)

def run_suite(dev: FFDevice, parallel: bool = True) -> list:
    """Run all applicable effects. Parallel up to min(n_effects, workers)."""
    tests = list(SUITE)

    if parallel and dev.n_effects > 1:
        workers = min(dev.n_effects, len(tests), 4)
        results = []
        order = [nm for nm, *_ in tests]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futs = {
                pool.submit(_run_one, dev, nm, co, fa, du): nm
                for nm, co, fa, du in tests
            }
            for fut in as_completed(futs):
                results.append(fut.result())
        results.sort(key=lambda r: order.index(r["name"])
                     if r["name"] in order else 999)
        return results
    else:
        return [_run_one(dev, nm, co, fa, du) for nm, co, fa, du in tests]

# ─── Device discovery (parallel, memoized) ────────────────────────────────────
@lru_cache(maxsize=1)
def find_ff_devices() -> list:
    """
    Scan all /dev/input/event* in parallel and return FF-capable devices,
    sorted by n_effects descending (best device first).
    Result is lru_cache-memoized — repeated calls cost nothing.
    """
    paths = evdev.list_devices()

    def _try(path):
        try:
            d = FFDevice(path)
            return d if d.is_ff else None
        except (PermissionError, OSError):
            return None

    with ThreadPoolExecutor(max_workers=min(8, len(paths) or 1)) as pool:
        hits = [r for r in pool.map(_try, paths) if r is not None]

    return sorted(hits, key=lambda d: d.n_effects, reverse=True)

# ─── Print helpers ────────────────────────────────────────────────────────────
FF_CODE_NAMES = {
    ec.FF_RUMBLE:     "RUMBLE",
    ec.FF_CONSTANT:   "CONSTANT",
    ec.FF_PERIODIC:   "PERIODIC",
    ec.FF_SPRING:     "SPRING",
    ec.FF_DAMPER:     "DAMPER",
    ec.FF_FRICTION:   "FRICTION",
    ec.FF_INERTIA:    "INERTIA",
    ec.FF_RAMP:       "RAMP",
    ec.FF_GAIN:       "GAIN",
    ec.FF_AUTOCENTER: "AUTOCENTER",
    ec.FF_SINE:       "SINE",
    ec.FF_SQUARE:     "SQUARE",
    ec.FF_TRIANGLE:   "TRIANGLE",
    ec.FF_SAW_UP:     "SAW_UP",
    ec.FF_SAW_DOWN:   "SAW_DOWN",
}

def fmt_codes(codes: set) -> str:
    names = [FF_CODE_NAMES.get(c, f"0x{c:02x}") for c in sorted(codes)]
    return "  ".join(names)

def print_results(results: list):
    for r in results:
        s = r["status"]
        if s == "ok":
            print(f"  {ok(r['name'])}")
        elif s == "skip":
            print(f"  {DIM}─ {r['name']:12s}  not supported{R}")
        else:
            print(f"  {err(r['name'])}  {DIM}{r['msg']}{R}")
    n_ok   = sum(1 for r in results if r["status"] == "ok")
    n_skip = sum(1 for r in results if r["status"] == "skip")
    n_fail = len(results) - n_ok - n_skip
    fail_c = RED if n_fail else DIM
    print(f"\n  {GRN}{n_ok} ok{R}  {DIM}{n_skip} skip{R}  {fail_c}{n_fail} fail{R}")

# ─── Interactive mode ─────────────────────────────────────────────────────────
def interactive(dev: FFDevice):
    print(hdr(f"  {dev.name}  [{dev.path}]"))
    print(inf(f"  n_effects={dev.n_effects}  ff_codes={len(dev.ff_codes)}"))
    print(inf(f"  {DIM}{fmt_codes(dev.ff_codes)}{R}"))

    if dev.n_effects == 0:
        print(wrn("  n_effects=0 — device will likely reject all effects."))
        print(inf("  Are you on the pidff-6 kernel?  "
                  "Check: grep '^default' /boot/extlinux/extlinux.conf"))

    applicable = [(nm, co, fa, du) for nm, co, fa, du in SUITE
                  if dev.supports(co)]
    if not applicable:
        print(err("  No supported effects on this device.")); return

    while True:
        print()
        for i, (nm, *_) in enumerate(applicable, 1):
            print(f"  {B}{i:2d}{R}. {nm}")
        print(f"\n   {B}a{R}. run all  (parallel, up to n_effects={dev.n_effects})")
        print(f"   {B}s{R}. run all  (sequential)")
        print(f"   {B}q{R}. quit")

        ch = input(f"\n{YLW}> {R}").strip().lower()
        if ch == 'q':
            break
        elif ch in ('a', 's'):
            par = (ch == 'a')
            print(inf(f"  Running {'parallel' if par else 'sequential'}…"))
            results = run_suite(dev, parallel=par)
            print_results(results)
        elif ch.isdigit() and 1 <= int(ch) <= len(applicable):
            nm, _, fa, du = applicable[int(ch) - 1]
            print(inf(f"  {nm}…"), end='', flush=True)
            ok_flag, msg = dev.play_effect(fa(), du)
            if ok_flag:
                print(f"\r{ok(nm)}     ")
            else:
                print(f"\r{err(nm)}  {DIM}{msg}{R}")

# ─── CLI entry point ──────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        prog="fftest2026",
        description="Modern Linux force feedback tester — Rock 5B+ / ARM64",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1].strip()
    )
    ap.add_argument("device",  nargs="?", metavar="/dev/input/eventN",
                    help="target device (auto-detected if omitted)")
    ap.add_argument("--list",  action="store_true",
                    help="list all FF-capable devices and exit")
    ap.add_argument("--batch", action="store_true",
                    help="run full suite non-interactively and print results")
    ap.add_argument("--json",  action="store_true",
                    help="JSON results to stdout (implies --batch)")
    ap.add_argument("--seq",   action="store_true",
                    help="sequential effect playback (safe for n_effects=1)")
    ap.add_argument("--gain",  type=int, default=75, metavar="0-100",
                    help="device gain before testing (default: 75)")
    args = ap.parse_args()

    if args.json:
        args.batch = True

    # ── Device selection ──────────────────────────────────────────────────────
    devices = find_ff_devices()  # cached after first call

    if args.list:
        if not devices:
            print(err("No FF-capable event devices found."))
            print(inf("Booted into pidff-6 kernel?  "
                      "Check: grep '^default' /boot/extlinux/extlinux.conf"))
            sys.exit(1)
        print(hdr("FF-capable devices (best first):"))
        for d in devices:
            print(f"\n  {GRN}{d.path}{R}  {B}{d.name}{R}")
            print(f"  n_effects={d.n_effects}  |  {DIM}{fmt_codes(d.ff_codes)}{R}")
        sys.exit(0)

    if args.device:
        try:
            dev = FFDevice(args.device)
        except (PermissionError, OSError) as ex:
            sys.exit(err(f"Cannot open {args.device}: {ex}"))
        if not dev.is_ff:
            print(wrn(f"{args.device} has no EV_FF capability — probably wrong device."))
            print(inf("Run --list to see all FF devices."))
    elif devices:
        dev = devices[0]
        print(inf(f"Auto-selected: {GRN}{dev.path}{R}  {dev.name}"))
    else:
        print(err("No FF-capable devices found."))
        print(inf("Suggestions:"))
        print(inf("  1. Boot into pidff-6 kernel:  "
                  "grep '^default' /boot/extlinux/extlinux.conf  → must say  default l3"))
        print(inf("  2. Load joydev:    sudo modprobe joydev"))
        print(inf("  3. Check devices:  ls -la /dev/input/event*"))
        print(inf("  4. Check dmesg:    dmesg | grep -i 'pidff\\|hid\\|joystick\\|input'"))
        sys.exit(1)

    if dev.n_effects == 0:
        print(wrn(f"n_effects=0 on {dev.path}  — FF effects will likely fail."))
        print(inf("This usually means wrong kernel (need pidff-6) or device not recognised."))
        if not args.batch:
            print(inf("Continuing anyway — run --list to compare all event devices."))

    dev.gain(args.gain)

    # ── Run ───────────────────────────────────────────────────────────────────
    if args.batch:
        parallel = not args.seq
        print(inf(f"Testing {B}{dev.name}{R}  "
                  f"({'parallel x' + str(min(dev.n_effects,4)) if parallel else 'sequential'})"))
        results = run_suite(dev, parallel=parallel)

        if args.json:
            out = {
                "device": dev.path,
                "name":   dev.name,
                "n_effects": dev.n_effects,
                "ff_code_count": len(dev.ff_codes),
                "ff_codes": sorted(dev.ff_codes),
                "results": results,
            }
            print(json.dumps(out, indent=2))
        else:
            print_results(results)
    else:
        interactive(dev)

if __name__ == "__main__":
    main()
