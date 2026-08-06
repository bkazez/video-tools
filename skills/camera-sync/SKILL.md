---
name: camera-sync
description: Load BEFORE syncing camera footage to audio recorded on a separate device — lining a clip up with a multitrack session, finding which clip covers which take, or working out why a clip's duration does not match the time it occupies. Also load when camera audio is silent or unusable, when a clip is or might be slow motion (S&Q), or when a task mentions rtmd, XAVC, camera timecode, clip wall clock, or clock drift between a camera and a recorder.
---

# Syncing a camera to a separate recorder

The normal method — correlate the camera's scratch audio against the recording —
fails often enough that it should never be the only plan. This is what to do
instead, in the order the questions actually arise.

Tools are in `~/Projects/video-tools/bin/`.

## Ask the clip what it is before doing anything else

    sony-clip-info Video/                  # every clip in a folder
    sony-clip-info --deep --verify CLIP.MP4

Run this first, always. It reads the camera's own real-time metadata track and
reports the camera model, the **capture frame rate**, shutter, ISO, white
balance, the embedded monitoring LUT, the start timecode and a **wall clock**.

Three of those change what you do next, and none are visible to `ffprobe`.

### Slow motion is the trap that invalidates everything upstream

In S&Q mode a camera captures at one rate and writes the file at another. The
container then declares a duration that is a multiple of the time the clip
really occupies. Every calculation built on that duration is wrong, and wrong in
a way that looks like a clock problem rather than a duration problem: clips
appear to overlap each other, gaps come out negative, and no offset fits.

`sony-clip-info` states the factor outright, from the capture rate in the
metadata. `--verify` confirms it independently by reading the wall clock at the
first and last frame.

The fix is lossless, because every captured frame is in the file. In Resolve,
override the clip's **FPS** to the capture rate (see the `davinci-resolve`
skill); in ffmpeg, `setpts=PTS/factor`.

**A silent audio track corroborates it.** Sony records no audio at all in S&Q,
so an all-zero PCM track is not a dead microphone — it is the clip telling you it
is slow motion. `--deep` checks for this.

### The clip's wall clock is the thing you actually sync with

Camera clocks are wrong, recorder clocks are wrong, and neither matters: the
*difference* between them is constant over a session and can be recovered.

## Solve the clock offset from roll-starts

    camera-session-sync Video/ Media/ --project "Session.RPP"

An operator starts the camera at the top of a take, so camera roll-starts pile
up near take starts. Every (roll-start, anchor) pair proposes an offset and the
true one is what many pairs agree on.

**Pass `--project`.** Recorder file starts alone are a weak set of anchors: a
session that leaves the recorder running through an hour of takes offers one
file start for a dozen performances, and most clips vote for nothing. The
region starts in the edit are the moments someone actually pressed record. On
one session this took the consensus from 3 votes to 5 and moved the answer.

**This is a starting point, not an answer.** On `2026-04-07 Brahms Faure` it
returned 194 s and the truth was 183.7 — ten seconds out, from a cluster of five
agreeing pairs with a 4 s spread, including three roll-starts that landed within
a second of a take start. It looked like a lock and was not. An operator does not
press record at a repeatable moment relative to the downbeat, so the cluster is
genuinely wide and its centre is not the offset. Treat the result as a place to
begin checking, and **never build a timeline on it unverified** — ten seconds is
a nudge on a one-minute take and ruins a six-minute one.

Two things to check in the output rather than trusting the number:

- **How many pairs agreed, and the spread.** A handful of agreeing clips with a
  spread inside a couple of seconds is a real lock. One or two is a coincidence.
- **`--track`.** Region times are read through whichever item sits under them, so
  the reference track must be a main mic. Point it at a second recorder's track —
  a room pair on its own box — and every region silently reports a wall clock
  from a device whose clock is hours off. The default is the first track holding
  audio, which is usually right and is worth confirming.

Accuracy is bounded by the coarser clock. A Sony acquisition clock ticks in whole
seconds, so this lands within about a second: enough to find the right clip and
the right minute, not enough for lip sync.

## Close the last second

    motion-sync CLIP.MP4 TAKE.wav --at 6.6 --window 4 --capture-fps 50

Players move when they play, so picture motion and audio loudness share a rhythm
even though neither is a copy of the other. Correlating their derivatives inside
a narrow window around a known-approximate offset can find the frame.

**It is a refinement, never a search.** Over a whole clip it will return a
confident wrong answer, because a performance is full of moments that resemble
other moments. Always pass a guess and a window of a few seconds.

**Believe the confidence report.** A weak margin means weak, and the tool says
so. On a locked-off close-up of a player's hands, continuous motion swamps the
onsets and it will not lock at all — that is the tool working correctly.

**Expect it to fail on sustained music.** It has never yet produced a usable
answer on this repertoire. On a singer in a church, three windows over the same
clip returned offsets 140 seconds apart, all with margins near zero: a singer's
head moves continuously and on phrase shapes, not on onsets, so there is little
for the flux to key on. It is worth one attempt because it costs a few minutes;
it is not worth arguing with.

Two ways to waste an afternoon here, both committed on the Brahms Faure session:

- **Sampling a slow-motion clip at the wrong rate.** To land samples every 1/F of
  *real* time, the file must be sampled at `F / factor`, because its own timeline
  runs `factor` times longer than real time. Multiplying instead of dividing
  stretches the motion signal by factor-squared and it correlates with nothing —
  which reads exactly like "this method does not work" rather than like a bug.
- **A reference with manufactured edges.** Assembling a session-wide envelope by
  pasting take files into a silent background puts a 40 dB step at every take
  boundary; those steps dominate the flux so completely that unrelated clips all
  "align" to the same one. Correlate against a single continuous recording.

## Verify by looking, because arithmetic cannot see a mouth

Never ship on the numbers. The check that settles it costs a minute:

1. Take the **isolated vocal or solo mic**, not the mix — "loud" in a mix is
   often the accompaniment, and a check built on it produces contradictions that
   look like sync errors.
2. Find sustained phonation (well above the mic's own median) and true rests.
3. Pull the frame at each and look. Mouth open on the sung moments, shut on the
   rests.
4. For frame precision, find the sharpest onset from silence and step ±5 frames
   through it; the mouth should begin opening at the centre.

A one-second error is glaring under this test and invisible under any amount of
arithmetic.

**Use the isolated mic, and step 1 is not optional.** On a voice-and-organ
session the mix is loud through the singer's rests, so "loud moments" picked off
the mix put an open mouth where there should be a closed one and the test
contradicts itself. Off the vocal mic alone the same test separated the correct
in-point from one ten seconds away on the first try.

## When nothing automatic works, one hand alignment is enough

Both automated routes can fail on the same session, and then the fastest path is
to have the person who can hear it align **one** take by hand, and derive
everything from that. Two clocks free-running over an evening keep a constant
difference, so a single good anchor fixes the whole session:

    offset = take_start_on_recorder − (camera_clock_at_clip_start + in_point)

Verify it on a take far away in time — an anchor set at the top of the evening
and confirmed ten minutes of camera clock later is worth more than any
correlation coefficient. On Brahms Faure an anchor from the Fauré held exactly
across to the Brahms, 640 s of camera clock later.

**Always leave picture handles.** Give every timeline ten seconds of video before
the audio and ten after. Sync will need nudging, and a timeline cut to the exact
take length runs out of frame the moment anyone tries.

## When the picture is not what you assumed

Before building anything, look at a frame from **each take's own window**, not
from the middle of the clip. Cameras get repointed mid-clip, and a clip whose
midpoint shows a music stand may be on the singer for the take you care about —
or the reverse.

A contact sheet answers it in one image:

    ffmpeg -ss T -i CLIP.MP4 -vframes 1 -vf "scale=426:240,<log-to-709>" f.png
    ffmpeg -framerate 1 -i "%02d.png" -vf "tile=5x5:padding=6" -frames:v 1 sheet.png

This is worth doing before any editorial decision, and it is the step that
catches "the only camera rolling during the chosen take was pointed at someone
else". Which has happened: on `2026-04-07 Brahms Faure` the chosen Fauré render
turned out to be covered only by a close-up of the organist's hands, while the
take the singer had rejected was the one with him on camera.

Two shell notes, both of which have cost time here: `zsh` aborts a command line
on a glob that matches nothing, so clear a directory with `find … -delete` rather
than `rm dir/*.png`; and this machine's `ffmpeg` has no `drawtext` filter, so
label a contact sheet by tracking the order rather than burning text in.
