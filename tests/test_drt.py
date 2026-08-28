#!/usr/bin/env python3
"""The DRT read/edit/write path, on a .drt built here rather than exported.

    python3 tests/test_drt.py

A synthesised archive is the whole point: it can hold the awkward cases a real
export happens not to have on the day -- a sub-frame `123|<hex double>`
remainder, an empty `<In/>`, a still beside a moving clip, a transition -- and it
proves the surgical edit leaves everything it did not mean to touch alone, which
is the property a diff of two 350 kB files cannot show.

What this file CANNOT prove is that Resolve accepts the result, so it is only
half the check. The other half runs on every real invocation:
`bin/resolve-ripple` re-reads the imported timeline, compares it against the plan
it made, and renders matched frames out of both timelines against a
same-frame-twice floor. Measured 2026-08-27 on `Polyphemus Horizontal`, that
picture check reads 3.24 for the DRT round trip this module writes and 37.8-91.0
for an OTIO round trip that lost 28 of 54 grades -- which is the control saying
the check can tell the two apart.
"""
import io
import os
import struct
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import drt as D

TIMELINE_ID = "11111111-1111-4111-8111-111111111111"
SEQUENCE_ID = "22222222-2222-4222-8222-222222222222"

FPS_HEX = struct.pack("<dd", 25.0, 0.0).hex()
EXTENTS_HEX = struct.pack("<dd", 0.0, 40.0).hex()

PASSED = FAILED = 0


def check(name, got, want):
    global PASSED, FAILED
    if got == want:
        PASSED += 1
        print(f"  ok   {name}")
    else:
        FAILED += 1
        print(f"  FAIL {name}: {got!r} != {want!r}")


def in_element(src_in):
    """A transition has no <In> at all; a clip that starts at its source's first
    frame writes an empty one. Both are in this fixture on purpose."""
    return "" if src_in is None else f"       <In>{src_in}</In>\n"


def clip(tag, dbid, name, start, duration, src_in, extra=""):
    """One item, shaped like Resolve's -- including a tag no XML parser accepts."""
    return f"""     <Element>
      <{tag} DbId="{dbid}">
       <Name>{name}</Name>
       <Start>{start}</Start>
       <Duration>{duration}</Duration>
{in_element(src_in)}       <MediaFrameRate>{FPS_HEX}</MediaFrameRate>{extra}
       <pLmVerTable>
        <ListMgt::LmVersionTable DbId="{dbid[:-1]}9">
         <Body>THE GRADE FOR {name}</Body>
        </ListMgt::LmVersionTable>
       </pLmVerTable>
      </{tag}>
     </Element>"""


def track(kind, index, items):
    return f"""  <Element>
   <Sm2TiTrack DbId="3333333{index}-3333-4333-8333-333333333333">
    <Sequence>{SEQUENCE_ID}</Sequence>
    <Items>
{chr(10).join(items)}
    </Items>
   </Sm2TiTrack>
  </Element>"""


def build(path):
    video = track("video", 1, [
        clip("Sm2TiVideoClip", "aaaaaaaa-0001-4000-8000-000000000000", "shot-a.mov", 0, 100, ""),
        clip("Sm2TiVideoClip", "aaaaaaaa-0002-4000-8000-000000000000", "shot-b.mov", 100, 200, 500),
        clip("Sm2TiVideoClip", "aaaaaaaa-0003-4000-8000-000000000000", "shot-c.mov", 300, 100, 40),
        clip("Sm2TiTransition", "aaaaaaaa-0004-4000-8000-000000000000", "Transition", 390, 10, None),
    ])
    overlay = track("video", 2, [
        clip("Sm2TiVideoClip", "bbbbbbbb-0001-4000-8000-000000000000", "grid.png", 0, 400, 90000),
    ])
    audio = track("audio", 3, [
        clip("Sm2TiAudioClip", "cccccccc-0001-4000-8000-000000000000", "mix.wav",
             0, "400|000000000080d53f", 26),
    ])
    sequence = f"""<?xml version="1.0" encoding="UTF-8"?>
<!--DbAppVer="21.0.4.0005" DbPrjVer="17"-->
<Sm2SequenceContainer DbId="44444444-4444-4444-8444-444444444444">
 <VideoTrackVec>
{video}
{overlay}
 </VideoTrackVec>
 <AudioTrackVec>
{audio}
 </AudioTrackVec>
 <SubtitleTrackVec/>
</Sm2SequenceContainer>
"""
    project = f"""<?xml version="1.0" encoding="UTF-8"?>
<SM_Project DbId="55555555-5555-4555-8555-555555555555">
 <ProjectName>Synth</ProjectName>
 <TimelineHandleVec>
  <Element>{TIMELINE_ID}</Element>
 </TimelineHandleVec>
</SM_Project>
"""
    folder = f"""<?xml version="1.0" encoding="UTF-8"?>
<MpFolder DbId="66666666-6666-4666-8666-666666666666">
 <Sm2Timeline DbId="{TIMELINE_ID}">
  <Name>Synth</Name>
  <Sequence>
   <Sm2Sequence DbId="{SEQUENCE_ID}">
    <MediaExtents>{EXTENTS_HEX}</MediaExtents>
   </Sm2Sequence>
  </Sequence>
 </Sm2Timeline>
</MpFolder>
"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("project.xml", project)
        z.writestr("MediaPool/Master/MpFolder.xml", folder)
        z.writestr(f"SeqContainer/{SEQUENCE_ID}.xml", sequence)
        # A multicam clip's sequence, which is what makes "the biggest file" the
        # wrong way to find the timeline on a project whose timeline is short.
        z.writestr("SeqContainer/77777777-7777-4777-8777-777777777777.xml",
                   sequence.replace(SEQUENCE_ID, "88888888-8888-4888-8888-888888888888")
                           .replace("44444444", "99999999") + " " * 100000)
    return path


def positions(doc):
    return {f"{t.kind}{t.index}": [(i.name, i.start.frames, i.duration.frames,
                                    i.src_in.frames if i.src_in else None)
                                   for i in t.items] for t in doc.tracks}


def main():
    work = tempfile.mkdtemp(prefix="test-drt-")
    source = build(os.path.join(work, "synth.drt"))

    doc = D.Timeline(source)
    print("reading")
    check("the timeline's own sequence is found, not the bigger multicam one",
          doc.seq_name, f"SeqContainer/{SEQUENCE_ID}.xml")
    check("frame rate", doc.frame_rate, 25.0)
    check("tracks", [f"{t.kind}{t.index}" for t in doc.tracks],
          ["video1", "video2", "audio1"])
    check("an empty <In/> reads as frame 0",
          doc.tracks[0].items[0].src_in.frames, 0)
    check("a sub-frame duration keeps its remainder",
          str(doc.tracks[2].items[0].duration), "400|000000000080d53f")
    check("a still is recognised by its extension",
          [i.is_still for i in doc.tracks[1].items], [True])
    check("end frame", doc.end_frame, 400)

    print("\nrippling: 25 frames at 150, inside shot-b")
    report = doc.ripple(150, 25, straddle="split", extend=("mix.wav",))
    out = D.Timeline(doc.write(os.path.join(work, "out.drt")))
    now = positions(out)
    check("shot-a is untouched", now["video1"][0], ("shot-a.mov", 0, 100, 0))
    check("shot-b is cut at the point", now["video1"][1], ("shot-b.mov", 100, 50, 500))
    check("its tail moves by 25 and picks up the source it left off at",
          now["video1"][2], ("shot-b.mov", 175, 150, 550))
    check("shot-c moves", now["video1"][3], ("shot-c.mov", 325, 100, 40))
    check("the transition moves", now["video1"][4], ("Transition", 415, 10, None))
    check("the still is extended rather than cut", now["video2"], [("grid.png", 0, 425, 90000)])
    check("the media that got longer is extended",
          now["audio1"][0][:3], ("mix.wav", 0, 425))
    check("and keeps its sub-frame remainder",
          str(out.tracks[2].items[0].duration), "425|000000000080d53f")
    check("the sequence's length in seconds follows", round(seconds(out), 3), 41.0)

    print("\nwhat the edit must NOT have touched")
    grades = lambda text: sorted(line.strip() for line in text.splitlines()
                                 if "<Body>" in line)
    check("every grade survives, and the split clip's is copied to both halves",
          grades(out.text), sorted(grades(doc.text)
                                   + ["<Body>THE GRADE FOR shot-b.mov</Body>"]))
    halves = [i for i in out.tracks[0].items if i.name == "shot-b.mov"]
    dbids = [D._DBID.findall(out.text[i.element.start:i.element.end]) for i in halves]
    check("the two halves of the split clip share no DbId",
          set(dbids[0]) & set(dbids[1]), set())
    check("and the copy has as many ids as the original",
          len(dbids[1]), len(dbids[0]))
    check("no DbId in the file is used twice",
          len(D._DBID.findall(out.text)), len(set(D._DBID.findall(out.text))))
    check("the multicam sequence in the same archive is byte-identical",
          zipfile.ZipFile(source).read("SeqContainer/77777777-7777-4777-8777-777777777777.xml"),
          zipfile.ZipFile(os.path.join(work, "out.drt")).read(
              "SeqContainer/77777777-7777-4777-8777-777777777777.xml"))

    print("\nthe other straddle modes")
    doc = D.Timeline(source)
    doc.ripple(150, 25, straddle="repeat")
    now = positions(D.Timeline(doc.write(os.path.join(work, "repeat.drt"))))
    check("repeat runs the left half on into the hole",
          now["video1"][1], ("shot-b.mov", 100, 75, 500))
    check("and the right half still starts where it did",
          now["video1"][2], ("shot-b.mov", 175, 150, 550))

    doc = D.Timeline(source)
    doc.ripple(150, 25, straddle="extend")
    now = positions(D.Timeline(doc.write(os.path.join(work, "extend.drt"))))
    check("extend leaves one clip, longer", now["video1"][1],
          ("shot-b.mov", 100, 225, 500))

    print("\ntaking time out")
    doc = D.Timeline(source)
    doc.ripple(150, -25, straddle="split", extend=("mix.wav", "grid.png"))
    now = positions(D.Timeline(doc.write(os.path.join(work, "back.drt"))))
    check("the tail comes back by 25", now["video1"][2], ("shot-b.mov", 125, 150, 550))
    check("shot-c comes back too", now["video1"][3], ("shot-c.mov", 275, 100, 40))

    print("\nwhat it refuses")
    for name, at, by, kwargs in (
            ("a removal that would swallow a clip", 90, -120, {}),
            ("a removal that runs off the straddled clip", 290, -60, {}),
            ("a point inside a transition", 395, 25, {}),
            ("--by 0", 150, 0, {}),
            ("repeat while removing time", 150, -25, {"straddle": "repeat"}),
            ("an unknown straddle mode", 150, 25, {"straddle": "sideways"})):
        doc = D.Timeline(source)
        try:
            doc.ripple(at, by, **kwargs)
            check(name, "went ahead", "refused")
        except D.DrtError:
            check(name, "refused", "refused")

    print(f"\n{PASSED} ok, {FAILED} failed")
    return 1 if FAILED else 0


def seconds(doc):
    import re
    text = doc.members["MediaPool/Master/MpFolder.xml"].decode()
    raw = re.search(r"<MediaExtents>([0-9a-f]{32})</MediaExtents>", text).group(1)
    return struct.unpack("<dd", bytes.fromhex(raw))[1]


if __name__ == "__main__":
    sys.exit(main())
