"""Driving DaVinci Resolve, and checking that what it did is what was asked.

Shared by `bin/resolve-ripple` and `bin/resolve-conform`, which both work the
same way and for the same reason: the Resolve API cannot move a clip -- there is
no `TimelineItem.SetStart` -- so an edit that changes where things sit has to
leave Resolve as a `.drt`, be made on the file (see `lib/drt.py`), and be
imported back. What is here is the half that touches Resolve: opening it,
reading a timeline in a way that means the same thing twice, and proving the
timeline that came back is the one that was planned.
"""
import os
import shutil
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append("/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
                "Developer/Scripting/Modules")
os.environ.setdefault(
    "RESOLVE_SCRIPT_LIB",
    "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/"
    "Fusion/fusionscript.so")

REFRAME = ("ZoomX", "ZoomY", "Pan", "Tilt", "RotationAngle", "AnchorPointX",
           "AnchorPointY", "CropLeft", "CropRight", "CropTop", "CropBottom",
           "Opacity", "FlipX", "FlipY")

TOOL = os.path.basename(sys.argv[0]) or "resolve"


def die(message):
    sys.exit(f"{TOOL}: {message}")


def connect():
    try:
        import DaVinciResolveScript as dvr
    except ImportError:
        die("Resolve's scripting module is not on the path")
    resolve = dvr.scriptapp("Resolve")
    if not resolve:
        die("Resolve is not running (open it, and set External scripting to Local)")
    project = resolve.GetProjectManager().GetCurrentProject()
    if not project:
        die("no project is open")
    return resolve, project


def timelines(project):
    return [project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1)]


def parse_time(text, fps, what):
    """`00:01:06:20`, `1:07.8`, `67.8`, `67.8s` or `1670f`, as whole frames."""
    text = text.strip()
    sign = -1 if text.startswith("-") else 1
    text = text.lstrip("+-")
    if text.endswith("f"):
        return sign * int(round(float(text[:-1])))
    if re.fullmatch(r"\d+:\d\d:\d\d:\d\d", text):
        h, m, s, f = (int(p) for p in text.split(":"))
        return sign * int(round(((h * 60 + m) * 60 + s) * fps + f))
    if re.fullmatch(r"\d+:\d\d(\.\d+)?", text):
        m, s = text.split(":")
        return sign * int(round((int(m) * 60 + float(s)) * fps))
    try:
        return sign * int(round(float(text.rstrip("s")) * fps))
    except ValueError:
        die(f"{what} {text!r} is not a timecode, a number of seconds or a frame count")


def timecode(frame, fps):
    frame = int(round(frame))
    per_minute, per_hour = int(round(fps)) * 60, int(round(fps)) * 3600
    h, rest = divmod(frame, per_hour)
    m, rest = divmod(rest, per_minute)
    s, f = divmod(rest, int(round(fps)))
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


def api_items(timeline):
    """Every item, in the order lib/drt.py reads them, so the two can be paired."""
    out = []
    for kind in ("video", "audio", "subtitle"):
        for track in range(1, timeline.GetTrackCount(kind) + 1):
            for item in timeline.GetItemListInTrack(kind, track) or []:
                out.append((f"{kind}{track}", item))
    return out


def fingerprint(project, timeline, under):
    """Every item of `timeline`, read while `under` is the current timeline.

    `under` is not decoration. `TimelineItem.GetProperty("Pan")` and `"Tilt"`
    are reported in the CURRENT timeline's pixel space rather than the item's
    own, so the same clip reads 175.68 with a 1920x1080 timeline open and 98.82
    with a 1080x1920 one -- 16/9 apart, on a clip nobody touched. Comparing a
    reading taken before an edit against one taken after it, with a different
    timeline open in between, therefore reports every reframe in the project as
    lost. Measured 2026-08-27; both readings come back identical once the
    current timeline is pinned.
    """
    project.SetCurrentTimeline(under)
    origin = timeline.GetStartFrame()
    rows = []
    for where, item in api_items(timeline):
        row = {"where": where, "name": item.GetName(),
               "start": item.GetStart() - origin, "end": item.GetEnd() - origin,
               "src_in": item.GetLeftOffset()}
        if where.startswith("video"):
            try:
                row["nodes"] = item.GetNumNodes()
            except Exception:
                row["nodes"] = None
            for prop in REFRAME:
                row[prop] = item.GetProperty(prop)
        rows.append(row)
    return rows


def drt_origin(timeline, doc):
    """How the DRT counts frames against how the API does, measured not assumed."""
    pairs = list(zip(api_items(timeline), doc.items))
    if len(pairs) != len(doc.items) or len(doc.items) != len(api_items(timeline)):
        die(f"{timeline.GetName()!r}: the export holds {len(doc.items)} items and "
            f"the timeline {len(api_items(timeline))}; refusing to guess which is which")
    offsets = {api.GetStart() - item.start.frames for (_, api), item in pairs}
    if len(offsets) != 1:
        die(f"{timeline.GetName()!r}: the export and the timeline disagree about "
            f"where clips are (offsets {sorted(offsets)}); refusing to edit it")
    # The second reading. An empty <In/> is read as frame 0 and a clone's source
    # in-point is arithmetic on it, so this is where that reading is checked.
    wrong = [(api.GetName(), api.GetLeftOffset(), item.src_in.frames)
             for (_, api), item in pairs
             if item.src_in is not None and api.GetLeftOffset() != item.src_in.frames]
    if wrong:
        die(f"{timeline.GetName()!r}: the export and the timeline disagree about "
            f"source in-points, first {wrong[0]}; refusing to edit it")
    return offsets.pop()


def joins(rows):
    """Adjacent pieces that are one clip: same clip, meeting in the timeline and
    running straight on in the source, with the same grade and the same reframe.
    Anything less is a cut somebody made on purpose -- a multicam angle change
    runs straight through the source too, and is told apart by the name, which
    carries the angle."""
    out = []
    rows = sorted(rows, key=lambda r: (r["where"], r["start"]))
    for left, right in zip(rows, rows[1:]):
        if left["where"] != right["where"] or left["name"] != right["name"]:
            continue
        if right["start"] != left["end"]:
            continue
        if right["src_in"] != left["src_in"] + (left["end"] - left["start"]):
            continue
        if any(left.get(k) != right.get(k) for k in ("nodes", *REFRAME)):
            continue
        out.append((left, right))
    return out


def mergeable(before, rows):
    """The joins THIS edit closed, and only those.

    A timeline can already hold a through edit -- an overlay cut in two that
    runs straight on, a clip somebody bladed and never moved -- and closing one
    is an edit nobody asked for. It happened: an overlay's own join at frame 197
    was silently merged away. So a pair only counts if it was not already a join
    before, which is exactly what a ripple that gets undone leaves behind.
    """
    def name(pair):
        left, right = pair
        return (left["where"], left["name"], left["src_in"], right["src_in"])

    was = {name(p) for p in joins(before)}
    return [p for p in joins(rows) if name(p) not in was]


def mergeable(before, rows):
    """The joins THIS edit closed, and only those.

    A timeline can already hold a through edit -- an overlay cut in two that
    runs straight on, a clip somebody bladed and never moved -- and closing one
    is an edit nobody asked for. It happened: an overlay's own join at frame 197
    was silently merged away. So a pair only counts if it was not already a join
    before, which is exactly what a ripple that gets undone leaves behind.
    """
    def name(pair):
        left, right = pair
        return (left["where"], left["name"], left["src_in"], right["src_in"])

    was = {name(p) for p in joins(before)}
    return [p for p in joins(rows) if name(p) not in was]


def planned(before, report, at, by):
    """What the fingerprint MUST read afterwards, derived from the plan alone.

    Written against the plan rather than against the result, because a check
    that reads the new timeline and asks whether it looks reasonable would pass
    on any edit at all.
    """
    extended = {(w, i.start.frames) for w, i in report["extended"]}
    split = {(s["where"], s["item"].start.frames): s for s in report["split"]}
    want, expect_new = [], []
    for row in before:
        key = (row["where"], row["start"])
        if row["start"] >= at:
            want.append(dict(row, start=row["start"] + by, end=row["end"] + by))
        elif key in extended:
            want.append(dict(row, end=row["end"] + by))
        elif key in split:
            piece = split[key]
            want.append(dict(row, end=at + (by if piece["mode"] == "repeat" else 0)))
            expect_new.append(dict(row, start=piece["tail_start"],
                                   end=piece["tail_start"] + piece["tail"],
                                   src_in=row["src_in"] + piece["head"]))
        else:
            want.append(row)
    return want, expect_new


def compare(want, expect_new, after):
    """Every way the round trip could have quietly lost something."""
    faults = []
    if len(after) != len(want) + len(expect_new):
        return [f"{len(after)} items came back against "
                f"{len(want) + len(expect_new)} planned"]
    index = {}
    for row in after:
        index.setdefault((row["where"], row["name"]), []).append(row)
    for row in want + expect_new:
        found = next((c for c in index.get((row["where"], row["name"]), [])
                      if c["start"] == row["start"]), None)
        if found is None:
            faults.append(f"{row['name']!r} on {row['where']} is not at "
                          f"frame {row['start']} any more")
            continue
        for key in ("end", "src_in", "nodes", *REFRAME):
            if key in row and row[key] != found[key]:
                faults.append(f"{row['name']!r} on {row['where']} at {row['start']}: "
                              f"{key} {row[key]!r} -> {found[key]!r}")
    return faults


def grab(project, timeline, frames, prefix, settle):
    """Export stills at `frames`, parking the playhead once per frame."""
    import time
    project.SetCurrentTimeline(timeline)
    time.sleep(settle)
    fps = float(timeline.GetSetting("timelineFrameRate"))
    out = {}
    for label, frame in frames:
        timeline.SetCurrentTimecode(timecode(timeline.GetStartFrame() + frame, fps))
        time.sleep(settle)
        path = f"{prefix}-{label}.png"
        if not project.ExportCurrentFrameAsStill(path):
            die(f"{timeline.GetName()!r}: Resolve refused to export frame {frame}")
        out[label] = path
    return out


def frame_check(resolve, project, old, new, shifts, settle):
    """Do the two timelines still RENDER the same picture where they should?

    The structural check reads node COUNTS and reframing properties, and a
    flattened grade with the right number of nodes would walk past it. This
    reads the picture instead, and it needs two things a bare tolerance cannot
    give it:

      a floor, because `ExportCurrentFrameAsStill` is not repeatable -- the same
      frame of the same timeline twice differs by a mean of about 3 counts on
      this material, so anything under that is the exporter, not the edit; and

      a control that FAILS, because on a held shot every frame matches every
      other one and a comparison that cannot tell them apart would pass however
      badly the grade had been lost. So each point also compares against a frame
      a second away, and a point where THAT matches too is reported as having
      proved nothing rather than counted as a pass.

    Measured 2026-08-27 on `Polyphemus Horizontal`: same frame twice, mean 2.6-2.9;
    a lossless DRT round trip, 1.6-3.2; two frames a second apart, 57.

    `shifts` is {frame of the old timeline: how far that frame moved}, because a
    conform moves different stretches of one timeline by different amounts and
    a single `by` could only ever check one of them.
    """
    sample = sorted(shifts)
    import numpy
    from PIL import Image

    resolve.OpenPage("color")
    work = tempfile.mkdtemp(prefix="resolve-ripple-frames-")
    control_gap = int(round(float(old.GetSetting("timelineFrameRate"))))
    try:
        def pixels(path):
            return numpy.asarray(Image.open(path).convert("RGB"), dtype=numpy.int32)

        def mean_difference(a, b):
            return float(numpy.abs(pixels(a) - pixels(b)).mean())

        was = grab(project, old, [(f"{f}a", f) for f in sample]
                   + [(f"{f}b", f) for f in sample], f"{work}/old", settle)
        shifted = [(f, f + shifts[f]) for f in sample]
        now = grab(project, new,
                   [(f"{f}m", g) for f, g in shifted]
                   + [(f"{f}c", g + control_gap) for f, g in shifted],
                   f"{work}/new", settle)

        floors, matches, blind = [], [], []
        for frame in sample:
            floor = mean_difference(was[f"{frame}a"], was[f"{frame}b"])
            match = mean_difference(was[f"{frame}a"], now[f"{frame}m"])
            control = mean_difference(was[f"{frame}a"], now[f"{frame}c"])
            floors.append(floor)
            matches.append((frame, match, floor))
            if control <= max(4 * floor, 4.0):
                blind.append(frame)
        return matches, blind
    finally:
        shutil.rmtree(work, ignore_errors=True)


