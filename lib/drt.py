"""Reading and editing a DaVinci Resolve timeline export (.drt).

A `.drt` is Resolve's OWN timeline format, and that is the whole reason this
module exists. Every other interchange format Resolve exports -- OTIO, AAF,
FCPXML, EDL -- describes an edit in somebody else's vocabulary, so a grade and a
reframe have nowhere to go. Measured on 2026-08-27 against the
`Polyphemus Horizontal` timeline (70 picture clips, 3-node grades, a 3.16x
vertical reframe): an OTIO round trip kept 70/70 cuts, **31/70 grades and 49/70
reframes**, while a DRT round trip kept **83/83 of cuts, source in-points, grade
node counts and every reframing property**, and matched frames exported from
both timelines agreed to within the still exporter's own repeatability (max
channel difference 31 against a same-frame-twice control of 33).

Inside, a `.drt` is a zip of pretty-printed XML:

    project.xml                     names the timeline handle
    MediaPool/Master/MpFolder.xml   the media, and the Sm2Timeline for the handle
    SeqContainer/<uuid>.xml         one per sequence: the timeline, and one per
                                    multicam clip

so the timeline's own file is found by following
`project.xml -> TimelineHandleVec` to an `Sm2Timeline` in `MpFolder.xml`, whose
`Sm2Sequence` DbId is what the tracks in one SeqContainer file name as their
`<Sequence>`. Picking "the biggest SeqContainer" would work on this project and
would silently pick a multicam clip on one whose timeline is short.

A clip is an element under a track's `<Items>` carrying `<Start>` (frames from
the timeline start), `<Duration>` and `<In>` (frames into its source). Values
are an integer, optionally `123|<8 bytes of little-endian double>` for a
sub-frame remainder, which is preserved untouched.

**Edits are applied to the original text**, never by re-serialising a parse:
Resolve's XML has element names like `ListMgt::LmVersionTable` that no XML
parser will accept, and the grade lives in base64-ish blobs that a round trip
through a parser has no reason to keep byte-identical. So this reads spans and
splices strings, and everything it did not mean to touch is unchanged by
construction.
"""
import io
import os
import re
import struct
import uuid
import zipfile

STILL_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".exr", ".dpx",
                    ".psd", ".bmp", ".gif", ".tga", ".webp"}

_TAG = re.compile(r"<(/?)([A-Za-z_][\w.:-]*)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>")
_DBID = re.compile(r'DbId="([0-9a-fA-F-]{36})"')


class DrtError(Exception):
    pass


class Node:
    """One XML element, as spans into the text it was read from."""

    __slots__ = ("tag", "start", "end", "body_start", "body_end", "children", "text_cache")

    def __init__(self, tag, start):
        self.tag = tag
        self.start = start
        self.end = self.body_start = self.body_end = None
        self.children = []

    def child(self, tag):
        for c in self.children:
            if c.tag == tag:
                return c
        return None

    def kids(self, tag):
        return [c for c in self.children if c.tag == tag]


def parse(text):
    """The element tree of `text`, tolerating tag names XML forbids."""
    root = Node("#doc", 0)
    root.body_start, root.body_end, root.end = 0, len(text), len(text)
    stack = [root]
    pos = 0
    while True:
        if text.startswith("<!--", pos):
            pos = text.index("-->", pos) + 3
            continue
        if text.startswith("<?", pos):
            pos = text.index("?>", pos) + 2
            continue
        m = _TAG.search(text, pos)
        if not m:
            break
        closing, tag, _, selfclose = m.groups()
        if closing:
            node = stack.pop()
            if node.tag != tag:
                raise DrtError(f"</{tag}> closes <{node.tag}> at offset {m.start()}")
            node.body_end, node.end = m.start(), m.end()
        elif selfclose:
            node = Node(tag, m.start())
            node.body_start = node.body_end = m.end()
            node.end = m.end()
            stack[-1].children.append(node)
        else:
            node = Node(tag, m.start())
            node.body_start = m.end()
            stack[-1].children.append(node)
            stack.append(node)
        pos = m.end()
    if len(stack) != 1:
        raise DrtError(f"unclosed <{stack[-1].tag}>")
    return root


class Value:
    """A frame count, keeping any `|<hex double>` sub-frame remainder as written."""

    __slots__ = ("frames", "suffix", "node")

    def __init__(self, raw, node):
        head, sep, rest = raw.partition("|")
        self.frames = int(head)          # empty is not a frame count; see Item
        self.suffix = sep + rest
        self.node = node

    def __repr__(self):
        return f"{self.frames}{self.suffix}"


class Item:
    """A clip or transition on a track."""

    def __init__(self, seq, element, node):
        self.seq = seq
        self.element = element          # the <Element> wrapper, which is what a clone copies
        self.node = node
        self.tag = node.tag
        self.name = seq._text(node.child("Name")) if node.child("Name") else ""
        self.start = Value(seq._text(node.child("Start")), node.child("Start"))
        self.duration = Value(seq._text(node.child("Duration")), node.child("Duration"))
        # A clip that starts at its source's first frame writes an empty <In/>
        # rather than a zero. Reading that as 0 is checked rather than assumed:
        # bin/resolve-ripple pairs every item against the API's GetLeftOffset().
        src_in = node.child("In")
        raw_in = (seq._text(src_in) if src_in is not None else "").strip()
        self.src_in = Value(raw_in or "0", src_in) if src_in is not None else None

    @property
    def end(self):
        return self.start.frames + self.duration.frames

    @property
    def is_transition(self):
        return self.tag.endswith("Transition")

    @property
    def is_still(self):
        return os.path.splitext(self.name)[1].lower() in STILL_EXTENSIONS

    def __repr__(self):
        return f"<{self.name!r} {self.start}+{self.duration}>"


class Track:
    def __init__(self, kind, index, items):
        self.kind = kind
        self.index = index
        self.items = items

    def __repr__(self):
        return f"<{self.kind}{self.index}: {len(self.items)} items>"


class Timeline:
    """The one timeline in a .drt, opened for editing."""

    def __init__(self, path):
        self.path = path
        with zipfile.ZipFile(path) as z:
            self.members = {n: z.read(n) for n in z.namelist()}
            self.order = list(z.namelist())
        self.seq_name = self._find_sequence_member()
        self.text = self.members[self.seq_name].decode("utf-8")
        self.root = parse(self.text)
        self.tracks = self._read_tracks()
        self._edits = []                 # (start, end, replacement) into self.text

    # -- locating the timeline's own sequence file -------------------------

    def _find_sequence_member(self):
        project = self.members["project.xml"].decode("utf-8")
        handles = re.search(r"<TimelineHandleVec>(.*?)</TimelineHandleVec>", project, re.S)
        ids = re.findall(r"<Element>([0-9a-fA-F-]{36})</Element>", handles.group(1)) if handles else []
        if len(ids) != 1:
            raise DrtError(f"{os.path.basename(self.path)} holds {len(ids)} timelines, expected 1")
        folder = self._member_text_containing(f'<Sm2Timeline DbId="{ids[0]}">')
        after = folder.split(f'<Sm2Timeline DbId="{ids[0]}">', 1)[1]
        seq = re.search(r'<Sm2Sequence DbId="([0-9a-fA-F-]{36})"', after)
        if not seq:
            raise DrtError("the timeline handle names no sequence")
        want = f"<Sequence>{seq.group(1)}</Sequence>"
        hits = [n for n in self.members
                if n.startswith("SeqContainer/") and want in self.members[n].decode("utf-8")]
        if len(hits) != 1:
            raise DrtError(f"{len(hits)} sequence files claim {seq.group(1)}, expected 1")
        self.sequence_id = seq.group(1)
        return hits[0]

    def _member_text_containing(self, needle):
        for name, blob in self.members.items():
            if name.startswith("MediaPool/"):
                text = blob.decode("utf-8")
                if needle in text:
                    return text
        raise DrtError("no media pool member names the timeline handle")

    # -- reading ------------------------------------------------------------

    def _text(self, node):
        return self.text[node.body_start:node.body_end]

    def _read_tracks(self):
        container = next((c for c in self.root.children if c.tag == "Sm2SequenceContainer"), None)
        if container is None:
            raise DrtError("no Sm2SequenceContainer in the sequence file")
        tracks = []
        for vec in container.children:
            if not vec.tag.endswith("TrackVec"):
                continue
            kind = vec.tag[:-len("TrackVec")].lower()
            for index, element in enumerate(vec.kids("Element"), 1):
                track_node = element.children[0]
                items_node = track_node.child("Items")
                items = []
                for wrapper in (items_node.kids("Element") if items_node else []):
                    items.append(Item(self, wrapper, wrapper.children[0]))
                tracks.append(Track(kind, index, items))
        return tracks

    @property
    def items(self):
        return [it for t in self.tracks for it in t.items]

    @property
    def frame_rate(self):
        m = re.search(r"<MediaFrameRate>([0-9a-fA-F]{32})</MediaFrameRate>", self.text)
        if not m:
            raise DrtError("the sequence declares no frame rate")
        return struct.unpack("<d", bytes.fromhex(m.group(1)[:16]))[0]

    @property
    def end_frame(self):
        return max((it.end for it in self.items), default=0)

    def clip_named(self, name):
        return [it for it in self.items if it.name == name]

    # -- editing ------------------------------------------------------------

    def _set(self, value, frames):
        self._edits.append((value.node.body_start, value.node.body_end,
                            f"{frames}{value.suffix}"))
        value.frames = frames

    def _clone_after(self, item, start, src_in, duration):
        """Queue a copy of `item` after it, at `start`, with fresh DbIds.

        The copy is built whole -- its Start, Duration and In rewritten in the
        copied text -- and inserted as ONE edit, because every other edit this
        class queues is an offset into the ORIGINAL text and an insertion cannot
        be allowed to move any of them.
        """
        text = self.text[item.element.start:item.element.end]
        for old in set(_DBID.findall(text)):
            text = text.replace(old, str(uuid.uuid4()))
        node = parse(text).children[0].children[0]
        for tag, value, source in (("Start", start, item.start),
                                   ("Duration", duration, item.duration),
                                   ("In", src_in, item.src_in)):
            child = node.child(tag)
            if child is None or value is None:
                continue
            text = (text[:child.body_start] + f"{value}{source.suffix}"
                    + text[child.body_end:])
            node = parse(text).children[0].children[0]      # spans moved
        line_start = self.text.rfind("\n", 0, item.element.start) + 1
        indent = self.text[line_start:item.element.start]
        self._edits.append((item.element.end, item.element.end,
                            "\n" + indent + text))

    def ripple(self, at, by, straddle="split", extend=(), split=()):
        """Insert `by` frames at timeline frame `at` (negative removes time).

        Everything starting at or after `at` moves by `by`. A clip the point
        falls INSIDE is the only interesting case, and there is no default that
        is right for every kind of material, so:

          split   cut it at `at` and move the right half, leaving a real hole --
                  a faithful ripple, and what a picture edit wants when the hole
                  is going to be filled by hand
          repeat  as split, but the left half plays `by` more frames of its own
                  source, so the hole is covered by material that is really
                  there and the shot repeats `by` frames
          extend  let it run `by` frames longer -- right for a still, and right
                  for the clip whose media is what got longer

        Stills always extend whatever the mode: there is nothing in a still to
        cut at, and splitting one would put a hole in an overlay.
        Names in `extend`/`split` override the mode for those clips.
        """
        if straddle not in ("split", "repeat", "extend"):
            raise DrtError(f"unknown straddle mode {straddle!r}")
        if by == 0:
            raise DrtError("--by 0 is not an edit")
        if by < 0 and straddle == "repeat":
            raise DrtError("--straddle repeat only makes sense when inserting time")

        report = {"moved": [], "extended": [], "split": [], "untouched": 0,
                  "at": at, "by": by, "was": {}}
        for track in self.tracks:
            for item in list(track.items):
                where = f"{track.kind}{track.index}"
                report["was"][id(item)] = (item.start.frames, item.duration.frames)
                if item.start.frames >= at:
                    if by < 0 and item.start.frames < at - by:
                        raise DrtError(
                            f"removing {-by} frames at {at} would swallow "
                            f"{item.name!r} on {where}")
                    self._set(item.start, item.start.frames + by)
                    report["moved"].append((where, item))
                elif item.start.frames < at < item.end:
                    mode = straddle
                    if item.name in extend:
                        mode = "extend"
                    elif item.name in split:
                        mode = "split"
                    elif item.is_still:
                        mode = "extend"
                    if item.is_transition and mode != "extend":
                        raise DrtError(
                            f"the point falls inside the transition on {where}; "
                            f"move it, or pass --straddle extend")
                    if mode == "extend":
                        self._set(item.duration, item.duration.frames + by)
                        report["extended"].append((where, item))
                    else:
                        head = at - item.start.frames
                        if by < 0 and item.duration.frames - head < -by:
                            raise DrtError(
                                f"removing {-by} frames at {at} runs off the end of "
                                f"{item.name!r} on {where}")
                        tail_in = (item.src_in.frames + head) if item.src_in else None
                        tail_duration = item.duration.frames - head
                        self._clone_after(item, at + by, tail_in, tail_duration)
                        self._set(item.duration,
                                  head + (by if mode == "repeat" else 0))
                        report["split"].append(
                            {"where": where, "item": item, "mode": mode,
                             "head": head, "tail": tail_duration,
                             "tail_start": at + by})
                else:
                    report["untouched"] += 1
        self._grow_media_extents(by)
        return report

    def _grow_media_extents(self, by):
        """The sequence records its length in seconds; keep it honest."""
        folder = next(n for n in self.members if n.startswith("MediaPool/"))
        text = self.members[folder].decode("utf-8")
        anchor = f'<Sm2Sequence DbId="{self.sequence_id}"'
        head, sep, tail = text.partition(anchor)
        if not sep:
            return
        m = re.search(r"<MediaExtents>([0-9a-fA-F]{32})</MediaExtents>", tail)
        if not m:
            return
        raw = bytes.fromhex(m.group(1))
        first, last = struct.unpack("<dd", raw)
        grown = struct.pack("<dd", first, last + by / self.frame_rate).hex()
        tail = tail[:m.start(1)] + grown + tail[m.end(1):]
        self.members[folder] = (head + sep + tail).encode("utf-8")

    # -- writing ------------------------------------------------------------

    def rename(self, name):
        """The name Resolve shows. The FILENAME is what actually decides it on
        import; this keeps the two from disagreeing when somebody reads the zip."""
        project = self.members["project.xml"].decode("utf-8")
        project = re.sub(r"<ProjectName>.*?</ProjectName>",
                         f"<ProjectName>{name}</ProjectName>", project, count=1)
        self.members["project.xml"] = project.encode("utf-8")

    def rendered(self):
        out = self.text
        for start, end, replacement in sorted(self._edits, key=lambda e: -e[0]):
            out = out[:start] + replacement + out[end:]
        return out

    def write(self, path):
        members = dict(self.members)
        members[self.seq_name] = self.rendered().encode("utf-8")
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            for name in self.order:
                z.writestr(name, members[name])
        with open(path, "wb") as fh:
            fh.write(buffer.getvalue())
        return path
