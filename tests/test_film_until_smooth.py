#!/usr/bin/env python3
"""film-until-smooth makes a film again only while it comes out jerky (exit 3).

    python3 tests/test_film_until_smooth.py
"""
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL = Path(__file__).resolve().parent.parent / "bin" / "film-until-smooth"
failures = []


def check(label, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{'' if ok else '  -- ' + detail}")
    if not ok:
        failures.append(label)


def tries(codes, limit=3):
    """Runs the tool on a command that exits with CODES in turn; how often it ran, and
    the tool's own exit."""
    with tempfile.TemporaryDirectory() as tmp:
        count = Path(tmp) / "count"
        count.write_text("0")
        script = (f"import pathlib,sys; p=pathlib.Path({str(count)!r}); n=int(p.read_text()); "
                  f"p.write_text(str(n+1)); sys.exit({codes!r}[min(n, {len(codes) - 1})])")
        done = subprocess.run([str(TOOL), "--tries", str(limit), "--", sys.executable, "-c", script],
                              capture_output=True, text=True)
        return int(count.read_text()), done.returncode


ran, code = tries([3, 3, 0])
check("jerky twice, then smooth: three runs, exit 0", (ran, code) == (3, 0), f"{ran} runs, exit {code}")
ran, code = tries([3])
check("jerky every time: stops at the limit, exit 3", (ran, code) == (3, 3), f"{ran} runs, exit {code}")
ran, code = tries([2])
check("any other failure: one run, its own exit", (ran, code) == (1, 2), f"{ran} runs, exit {code}")
ran, code = tries([0])
check("smooth at once: one run", (ran, code) == (1, 0), f"{ran} runs, exit {code}")
sys.exit(1 if failures else 0)
