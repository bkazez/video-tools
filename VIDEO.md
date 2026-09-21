# Video

Notes for working on picture, as MIXING.md is for sound.

## Resolve's API

- `TimelineItem.GetLeftOffset()` returns **timeline frames, not clip frames**.
  A clip with an FPS override — 50 fps S&Q footage in a 25 fps timeline —
  reports half the number its own rate would give, so dividing by the clip's
  FPS reads every source in-point at half its real value.
- `AppendToTimeline` honours `startFrame` on video and **ignores it on audio**.
  A film that must open past the talking at the head of a take gets there by
  rendering the audio already trimmed, not by trimming it in the timeline.

## Stacking angles, one per track

This is what Resolve itself builds: opening a multicam clip in a timeline
"replaces the contents of the Timeline with a vertical stack of superimposed
angles, one per track, each of which is offset from the beginning of the
Timeline to align with one another"
([manual, Opening and Altering Multicam Clips](https://www.steakunderwater.com/VFXPedia/__man/Resolve18-6/DaVinciResolve18_Manual_files/part1039.htm)).
Build a multi-angle edit that way rather than as one row of cuts:

- **One angle per track, highest track wins.** A shot is revealed by blading or
  disabling the tracks above it, not by moving anything, so lengthening or
  deleting a shot cannot open a hole under it.
- **The angle whose sync is still in doubt is ONE clip spanning the whole film,
  on the lowest track.** One clip is nudged once — select it and use `,` and
  `.`, the same keys the manual gives for sliding an angle inside a multicam
  clip — where several cuts of it have to be dragged into agreement one at a
  time. On the bottom it doubles as the fallback: any second no other angle
  covers shows it instead of black.
- **Name the tracks.** In a multicam clip the track name *is* the angle name;
  in a stack it is the only label that says which camera a row is.
- Resolve's scripting API has no multicam-clip constructor (`README.txt` under
  `Developer/Scripting` lists none), so a built project gets the stack and not
  the multicam clip. Converting one afterwards is by hand in the Media Pool.

## Checking a camera offset without camera audio

A roll has ONE constant. If the camera ran continuously across several takes,
then for every take on it

    camera clock - recorder clock = region start - measured offset

is the same number, so N takes give N estimates of one value and a wrong one is
visible without any further measurement. On a session where five takes agreed
inside 0.2 s, a sixth alignment 1.4 s out was a stale duplicate timeline, and
two hours went into measuring what that comparison answers in a minute.

Do that first. Only then reach for `motion-sync`, and read what it says about
itself: it refines a guess inside a few seconds and returns a confident wrong
answer over a whole clip. Correlating picture motion against loudness over a
wide search is the mistake it is warning about -- on legato singing it peaked
2.6 s from the truth with r = 0.09, while the same tool given a 6 s window
landed 0.24 s away with r = 0.21.

## Putting a timing curve into Resolve

Resolve's scripting API exposes `RetimeProcess` -- which interpolation a retime
uses -- and nothing that sets a speed or a retime keyframe. The way in is a
Fusion composition: `TimelineItem.ImportFusionComp(path)` takes a `.comp` as
text, so a curve with a keyframe per frame can be written and pushed.

    MediaIn1 -> TimeStretcher1 -> MediaOut1

with `TimeStretcher1.SourceTime` driven by a `BezierSpline` whose `KeyFrames`
are `[comp frame] = { source frame, Flags = { Linear = true } }`. `SourceTime`
counts in the comp's own frames at the TIMELINE rate, and comp frame 0 is the
clip's first frame, so the value wanted at frame k is
`donor_real_seconds * fps - GetLeftOffset()`.

Why bother, when ffmpeg can render a retimed file: the clip on the timeline
stays the camera's own media, so the grade runs on the original instead of on
an H.264 intermediate, and the curve is visible in the Fusion page. Rendering
cost nothing measurable -- 212 s of timeline took 19 s with the comp against 25
s without.

The one thing it cannot do is address a frame the timeline rate cannot reach:
50 fps S&Q footage conformed to a 25 fps timeline rounds `SourceTime` to 20 ms,
where `lipsync-clip --frame-exact` picks captured frames at 10 ms. Both are
well inside a 25 fps frame, and the two routes were checked against each other
on four sung entries -- same frame in each.

**Get the comp's shape by exporting one, never by guessing it:** add a comp with
`AddFusionComp()`, `ExportFusionComp(path, 1)`, and edit what comes out.
**Verify by rendering**, not with a still grab: `GrabStill` takes the current
clip rather than the playhead, so it will happily report a different shot
entirely -- here it returned the keys while the question was about the closeup.

## A global alignment is not lip sync

`arc warp` puts two takes on one clock and is right on average: across a 70 s
shot its median error at syllable onsets was 7 ms. It was also 218 ms wrong at
the worst one, which is five frames of lips out of step, and an average is no
defence against that.

So measure the thing that matters -- the error AT each onset, not the average
-- and pin the map to it. `warp-refine` finds onsets in both takes' unprocessed
spot, pairs the unambiguous ones, and bends the map so each pair meets: worst
error 218 ms to 85 ms on one shot, 208 ms to 112 ms on another.

Feed it the spot with its channel bypassed. A de-esser attenuates exactly the
sibilance an onset detector reads, and on this session the processed stem
nulled only 0.6 dB under the raw one.

Expect few anchors on legato singing: 26 in 70 s, and only two hard consonants
in the whole shot. That scarcity is also why picture-motion correlation keeps
coming back weak on this material -- there is very little to correlate.
