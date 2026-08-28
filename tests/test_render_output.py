#!/usr/bin/env python3
"""Which file bin/resolve-render decides its render wrote, with Resolve absent.

    python3 tests/test_render_output.py

The rule used to be "what is in the directory now, minus what was there when we
started", and the case it gets wrong is the ordinary one: re-rendering over a
file that is already there gains no NAME. On 2026-08-28 that exited 1 with
`the job says Complete and ... gained no file` while a complete 259 MB movie sat
in the directory -- and the cost was not the false alarm but that exiting there
skipped the ffprobe verification, so the run that most needed checking got none.

The control that matters is the pair: overwriting must be found, and a render
that really wrote nothing must still come back empty. A rule that answers "yes"
to both is not a check.
"""
import importlib.machinery
import importlib.util
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
LOADER = importlib.machinery.SourceFileLoader(
    "resolve_render", os.path.join(HERE, "..", "bin", "resolve-render"))
R = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("resolve_render", LOADER))
LOADER.exec_module(R)

PASSED = FAILED = 0


def check(name, got, want):
    global PASSED, FAILED
    if got == want:
        PASSED += 1
        print(f"  ok   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}: got {got!r}, want {want!r}")


def touch(d, name, when):
    p = os.path.join(d, name)
    open(p, "w").write("x")
    os.utime(p, (when, when))
    return p


def main():
    d = tempfile.mkdtemp()
    try:
        # A render that OVERWROTE the file already there. No new name; the rule
        # that subtracted the listing said "nothing was written".
        touch(d, "Polyphemus.mov", time.time() - 600)
        started = time.time()
        time.sleep(0.01)
        touch(d, "Polyphemus.mov", time.time())
        check("overwriting a file is found", R.written_since(d, started),
              os.path.join(d, "Polyphemus.mov"))

        # The control, and it has to fail: nothing written since the render began.
        started = time.time() + 60
        check("a render that wrote nothing is not found",
              R.written_since(d, started), None)

        # Two stale files and one fresh one: the fresh one, not the alphabetical
        # first, which is what `sorted(...)[0]` used to return.
        shutil.rmtree(d); os.makedirs(d)
        touch(d, "AAA older.mov", time.time() - 600)
        started = time.time()
        time.sleep(0.01)
        touch(d, "ZZZ newer.mov", time.time())
        check("the newest is chosen, not the first by name",
              R.written_since(d, started), os.path.join(d, "ZZZ newer.mov"))

        # A dotfile the OS drops in is not a render.
        shutil.rmtree(d); os.makedirs(d)
        started = time.time()
        time.sleep(0.01)
        touch(d, ".DS_Store", time.time())
        check("a dotfile is not the render", R.written_since(d, started), None)
    finally:
        shutil.rmtree(d, ignore_errors=True)

    print(f"\n{PASSED} ok, {FAILED} failed")
    sys.exit(1 if FAILED else 0)


if __name__ == "__main__":
    main()
