#!/usr/bin/env python3
"""What bin/resolve-conform decides, with neither Resolve nor arc running.

    python3 tests/test_conform.py

The decisions, and why each one is a decision rather than an obvious step:

  **the delta is a CLOCK delta, not a position delta.** A take whose clock did
  not move needs no picture change however much later the mix now ends, and a
  take whose clock moved needs its picture moved by that, not by how much longer
  the mix got. On the 2026-08-27 Polyphemus re-comp the mix grew 1.000 s while
  one item's `soffs` moved 0.181 s, so the two answers differ.

  **a camera clip follows the take it SHOWS**, which is the arc item it spends
  most of its time over -- not the one under its first frame, which for a clip
  cut a little before a join is the take before it.

  **a gap is closed only where the clips used to meet.** An overlay track is
  mostly gaps on purpose.

The other half -- that Resolve accepts the result and gives back the grades --
is checked on every real run, against the plan and against matched frames.
"""
import importlib.machinery
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
LOADER = importlib.machinery.SourceFileLoader(
    "resolve_conform", os.path.join(HERE, "..", "bin", "resolve-conform"))
C = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("resolve_conform", LOADER))
LOADER.exec_module(C)

PASSED = FAILED = 0


def check(name, got, want):
    global PASSED, FAILED
    if got == want:
        PASSED += 1
        print(f"  ok   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}: {got!r} != {want!r}")


def item(id, name, at, len_, soffs):
    return {"id": id, "name": name, "at": at, "len": len_, "soffs": soffs,
            "track": "AB"}


def main():
    print("what moved, per take")
    # The shape of the real re-comp: one take runs 0.82 s longer, the next
    # starts 0.18 s earlier in its own source, and the mix grows 1.00 s.
    was = [item("a", "take 6", 0.0, 52.9485, 0.0),
           item("b", "take 8", 52.9485, 15.0007, 55.6365),
           item("c", "take 7", 67.8213, 3.3347, 66.6012),
           item("d", "take 3", 71.1326, 20.0, 72.5049)]
    now = [item("a", "take 6", 0.0, 52.9485, 0.0),
           item("b", "take 8", 52.9485, 15.8215, 55.6365),
           item("c", "take 7", 68.64, 3.516, 66.4199),
           item("d", "take 3", 72.1326, 20.0, 72.5049)]
    spans, gone, added = C.clock_deltas(was, now)
    check("nothing is dropped or added", (gone, added), ([], 0))
    check("a take that only got longer has not moved", spans[1]["delta"], 0.0)
    check("the take after the join moved by its own clock, not by the mix's growth",
          round(spans[2]["delta"], 6), 1.0)
    check("and so does everything after it", round(spans[3]["delta"], 6), 1.0)
    check("the growth of the mix alone would have said something else",
          round((now[-1]["at"] + now[-1]["len"]) - (was[-1]["at"] + was[-1]["len"]), 4)
          != round(now[2]["soffs"] - was[2]["soffs"], 4), True)

    print("\nan item that is gone, or new")
    fewer, gone, added = C.clock_deltas(was, now[:-1])
    check("an item the re-comp removed is named, not counted -- picture cut "
          "over it is showing a take that is no longer in the mix",
          (len(fewer), [g["name"] for g in gone], added), (3, ["take 3"], 0))

    print("\nwhich take a moment belongs to")
    check("inside an item", C.delta_at(spans, 60.0)[1], "take 8")
    check("where two overlap, the incoming take wins",
          C.delta_at(spans, 67.9)[1], "take 7")
    check("before everything", C.delta_at(spans, -5.0)[1], "take 6 (before it)")
    check("after everything", C.delta_at(spans, 500.0)[1], "take 3 (after it)")

    print("\nwhich take a picture clip is showing")
    check("a clip wholly inside one take",
          C.majority(spans, 55.0, 60.0)["over"], "take 8")
    check("a clip cut a little before the join follows the take it spends its "
          "time over, not the one under its first frame",
          C.majority(spans, 67.0, 70.6)["over"], "take 7")
    check("and that is not what its first frame would have said",
          C.delta_at(spans, 67.0)[1], "take 8")
    check("the delta that comes with it",
          round(C.majority(spans, 67.0, 70.6)["delta"], 6), 1.0)
    check("a clip follows its OWN take where the comp uses it",
          C.majority(spans, 66.0, 70.0, take="take 7")["over"], "take 7")
    check("and follows the music where the comp uses its take nowhere near -- "
          "there is no clock of its own to follow there",
          C.majority(spans, 55.0, 58.0, take="take 7")["over"], "take 8")
    check("a clip of no take arc knows follows the music too",
          C.majority(spans, 55.0, 58.0, take="C0292.MP4")["over"], "take 8")

    print("\nmatching a take across the two applications")
    names = {"Polyphemus 1", "Polyphemus 3", "Polpyhemus 7", "Polyphemus 8"}
    check("an exact name matches itself",
          C.matches("Polyphemus 8", names), ("Polyphemus 8", False))
    check("a transposed name matches, and says it is spelled differently",
          C.matches("Polyphemus 7", names), ("Polpyhemus 7", True))
    check("and NOT the take whose number is different -- difflib scores "
          "'Polyphemus 1' above 'Polpyhemus 7' and put take 1's clock on take 7",
          C.matches("Polyphemus 7", names)[0] != "Polyphemus 1", True)
    check("a name that is nobody's take does not match",
          C.matches("C0292.MP4", names), (None, False))
    check("two arc items that reduce the same way are refused rather than picked",
          C.matches("Polyphemus 7", names | {"Polyhpemus 7"}), (None, False))
    check("a multicam angle comes off the name",
          C.take_of("Polyphemus 7 - Video 2"), "Polyphemus 7")

    print("\nwhich take replaced a deleted one")
    grew = [{"name": "take 8", "at": 52.9, "len": 7.1, "now_at": 52.9, "now_len": 15.0},
            {"name": "take 7", "at": 67.8, "len": 3.3, "now_at": 68.6, "now_len": 3.5}]
    dead = {"name": "take 3", "at": 59.9, "len": 8.0}
    check("the item that grew to fill it, read off the NEW positions",
          C.now_over(grew, dead), "take 8")
    check("and the old positions would have said nobody",
          C.delta_at(C.clock_deltas(
              [dict(g, id=g["name"], soffs=0) for g in grew] + [dict(dead, id="d", soffs=0)],
              [dict(g, at=g["now_at"], len=g["now_len"], id=g["name"], soffs=0)
               for g in grew])[0], 63.9)[1].endswith("(after it)"), True)

    print("\nclosing what the move opened")
    doc = Doc([Track("video1", [Clip(0, 100, 0), Clip(100, 50, 500), Clip(200, 40, 900)]),
               Track("video2", [Clip(0, 20, 0), Clip(400, 20, 0)])])
    met = C.abutting(doc)
    check("only the pair with nothing between them counts as meeting",
          [(w, l.start.frames) for w, l, _ in met], [("video1", 0)])
    doc.tracks[0].items[1].start.frames = 125
    closed = C.close_gaps(doc, met)
    check("the clip before the gap is lengthened to reach it",
          [(w, i.duration.frames, g) for w, i, g in closed], [("video1", 125, 25)])
    check("the overlay track's own spacing is left alone",
          [i.duration.frames for i in doc.tracks[1].items], [20, 20])

    doc = Doc([Track("video1", [Clip(0, 100, 0), Clip(100, 50, 500)])])
    met = C.abutting(doc)
    doc.tracks[0].items[1].start.frames = 80
    C.close_gaps(doc, met)
    check("an overlap shortens it instead",
          doc.tracks[0].items[0].duration.frames, 80)

    print(f"\n{PASSED} ok, {FAILED} failed")
    return 1 if FAILED else 0


class Value:
    def __init__(self, frames):
        self.frames = frames


class Clip:
    def __init__(self, start, duration, src_in):
        self.start, self.duration, self.src_in = Value(start), Value(duration), Value(src_in)
        self.name = "clip"

    @property
    def end(self):
        return self.start.frames + self.duration.frames


class Track:
    def __init__(self, where, items):
        self.kind, self.index, self.items = where[:-1], int(where[-1]), items


class Doc:
    def __init__(self, tracks):
        self.tracks = tracks

    def move(self, item, start=None, duration=None, src_in=None):
        if start is not None:
            item.start.frames = start
        if duration is not None:
            item.duration.frames = duration


if __name__ == "__main__":
    sys.exit(main())
