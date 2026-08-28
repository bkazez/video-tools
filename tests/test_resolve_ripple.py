#!/usr/bin/env python3
"""The parts of bin/resolve-ripple that decide things, without Resolve running.

    python3 tests/test_resolve_ripple.py

Two of them, and the second is the one that matters. `parse_time` turns what a
person types into frames, and a timecode read as seconds is a mistake nothing
downstream can catch. `compare` is the check that decides whether the edited
timeline replaces the original, so a check that passed whatever came back would
be worse than no check -- these cases hand it a result with a grade flattened, a
reframe reset, a clip left behind and a source in-point moved, and require it to
say so.
"""
import importlib.machinery
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
LOADER = importlib.machinery.SourceFileLoader(
    "resolve_ripple", os.path.join(HERE, "..", "bin", "resolve-ripple"))
RR = importlib.util.module_from_spec(importlib.util.spec_from_loader("resolve_ripple", LOADER))
LOADER.exec_module(RR)

PASSED = FAILED = 0


def check(name, got, want):
    global PASSED, FAILED
    if got == want:
        PASSED += 1
        print(f"  ok   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}: {got!r} != {want!r}")


class Item:
    """Enough of a lib/drt.py item for the report to be built by hand."""

    def __init__(self, name, start):
        self.name = name

        class V:
            frames = start
        self.start = V()


def row(where, name, start, end, src_in=0, nodes=3, zoom="1.0"):
    out = {"where": where, "name": name, "start": start, "end": end, "src_in": src_in}
    if where.startswith("video"):
        out["nodes"] = nodes
        out.update({prop: (zoom if prop == "ZoomX" else "0.0") for prop in RR.REFRAME})
    return out


def main():
    print("reading a time")
    for text, want in (("00:01:06:20", 1670), ("1:07.8", 1695), ("67.8", 1695),
                       ("67.8s", 1695), ("1670f", 1670), ("-25f", -25),
                       ("1s", 25), ("-1s", -25), ("00:00:00:00", 0)):
        check(f"{text!r} at 25 fps", RR.parse_time(text, 25.0, "--at"), want)
    check("and back to a timecode", RR.timecode(1670, 25.0), "00:01:06:20")
    check("a timecode is not read as seconds",
          RR.parse_time("00:01:06:20", 25.0, "--at") != RR.parse_time("1.0620", 25.0, "--at"),
          True)

    print("\nchecking the result against the plan")
    before = [row("video1", "a.mov", 0, 100),
              row("video1", "b.mov", 100, 300, src_in=500),
              row("video1", "c.mov", 300, 400),
              row("video2", "grid.png", 0, 400),
              row("audio1", "mix.wav", 0, 400)]
    report = {"moved": [("video1", Item("c.mov", 300))],
              "extended": [("video2", Item("grid.png", 0)),
                           ("audio1", Item("mix.wav", 0))],
              "split": [{"where": "video1", "item": Item("b.mov", 100),
                         "mode": "split", "head": 50, "tail": 150,
                         "tail_start": 175}],
              "untouched": 1, "at": 150, "by": 25}
    good = [row("video1", "a.mov", 0, 100),
            row("video1", "b.mov", 100, 150, src_in=500),
            row("video1", "b.mov", 175, 325, src_in=550),
            row("video1", "c.mov", 325, 425),
            row("video2", "grid.png", 0, 425),
            row("audio1", "mix.wav", 0, 425)]
    check("a round trip that kept everything passes",
          RR.compare(before, good, report, 150, 25), [])

    flattened = [dict(r) for r in good]
    flattened[2]["nodes"] = 1
    check("a grade flattened on the copied half is caught",
          any("nodes" in f for f in RR.compare(before, flattened, report, 150, 25)), True)

    reframed = [dict(r) for r in good]
    reframed[3]["ZoomX"] = "1.0000"
    check("a reframe reset is caught",
          any("ZoomX" in f for f in RR.compare(before, reframed, report, 150, 25)), True)

    moved = [dict(r) for r in good]
    moved[3]["start"] = 300
    check("a clip left where it was is caught",
          any("c.mov" in f for f in RR.compare(before, moved, report, 150, 25)), True)

    slipped = [dict(r) for r in good]
    slipped[2]["src_in"] = 500
    check("a source in-point that slipped is caught",
          any("src_in" in f for f in RR.compare(before, slipped, report, 150, 25)), True)

    check("a clip that did not come back at all is caught",
          RR.compare(before, good[:-1], report, 150, 25) != [], True)

    unextended = [dict(r) for r in good]
    unextended[5]["end"] = 400
    check("the media that should have got longer and did not is caught",
          any("mix.wav" in f for f in RR.compare(before, unextended, report, 150, 25)), True)

    print(f"\n{PASSED} ok, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
