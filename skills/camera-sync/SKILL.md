---
name: camera-sync
description: Load BEFORE syncing camera footage to audio recorded on a separate device — lining a clip up with a multitrack session, finding which clip covers which take, or working out why a clip's duration does not match the time it occupies. Also load when camera audio is silent or unusable, when a clip is or might be slow motion (S&Q), or when a task mentions rtmd, XAVC, camera timecode, clip wall clock, or clock drift between a camera and a recorder.
---

# Syncing a camera to a separate recorder

The usual method — correlate the camera's scratch audio against the recording —
fails whenever the camera's audio is silent, absent or useless, which is often.
This is what to do instead, in the order the questions arise.

Tools are in `~/Projects/video-tools/bin/`.

## Ask the clip what it is, first

    sony-clip-info Video/                  # every clip in a folder
    sony-clip-info --deep --verify CLIP.MP4

Reads the camera's own metadata track: model, **capture frame rate**, shutter,
ISO, white balance, embedded monitoring LUT, start timecode and a **wall clock**.
None of it is visible to `ffprobe`, and two of the fields decide everything that
follows.

### Slow motion invalidates every duration

In S&Q mode a camera captures at one rate and writes the file at another, so the
container declares a duration that is a multiple of the time the clip really
occupies. Every calculation built on that duration is wrong, and wrong in a way
that looks like a clock problem: clips appear to overlap, gaps come out negative,
no offset fits anything.

The factor is the capture rate over the container rate. `--verify` confirms it
independently from the wall clock at the first and last frame.

The correction is lossless — every captured frame is in the file. In Resolve,
override the clip's **FPS** to the capture rate (see the `davinci-resolve`
skill); in ffmpeg, `setpts=PTS/factor`.

**A silent audio track corroborates it.** Sony records no audio in S&Q, so an
all-zero PCM track is not a dead microphone, it is the clip saying it is slow
motion. `--deep` checks.

**S&Q is almost never what was wanted, and it costs the sync reference.** High frame
rate is available as an ordinary frame rate on the same bodies, with audio; S&Q is
the mode that bakes in the slow motion and drops the sound. Losing camera audio is
what forces hand-alignment later, so it is worth catching on the day rather than in
the edit:

    sony-clip-info --deep --expect profiles/sony-log-video.yml CLIP.MP4
    camera-card-check --install-agent      # or check every card at offload, hands-off

The profile asserts the settings a shoot can silently be wrong about — bit depth,
chroma, S&Q, audio present, ISO, shutter angle — and exits non-zero naming the one
that is off. Assume a camera has been reset or left on somebody else's settings
until a file says otherwise.

### The wall clock is what you sync with

Both clocks are wrong and it does not matter: the difference between them is
constant over a session and is what you are trying to recover.

## Get a first estimate from roll-starts

    camera-session-sync Video/ Media/ --project "Session.RPP"

An operator starts the camera near the top of a take, so roll-starts pile up near
take starts. Every (roll-start, anchor) pair proposes an offset; the winning
cluster is the estimate.

**Pass `--project`.** Recorder file starts alone are weak anchors — a session
that leaves the recorder running through an hour of takes offers one file start
for a dozen performances, and most clips vote for nothing. Region starts are the
moments someone actually pressed record.

**Set `--track` to a main mic.** Region times are read through whichever item
sits under them. A second recorder's track — a room pair on its own box — carries
that device's clock, which can be hours out, and every region silently inherits
it.

**Treat the result as a starting point and nothing more.** This method routinely
lands within a few seconds and can be ten seconds out while looking like a solid
lock: several agreeing pairs, a spread of a second or two, individual roll-starts
landing within a second of a take start. An operator does not press record at a
repeatable moment relative to the downbeat, so the cluster is genuinely wide and
its centre is not the answer. Its accuracy is also floored by the coarser clock —
an acquisition clock ticking in whole seconds cannot do better than about a
second.

Ten seconds is a nudge on a one-minute take and ruins a six-minute one, so
**never build a timeline on this unverified.**

## Content correlation, if the material suits it

    motion-sync CLIP.MP4 TAKE.wav --at 6.6 --window 4 --capture-fps 50

Players move when they play, so picture motion and audio loudness share a rhythm.
Correlating their derivatives inside a narrow window around a known-approximate
offset can find the frame.

**It is a refinement, never a search.** Over a whole clip it will return a
confident wrong answer — a performance is full of moments resembling other
moments. Always give it a guess and a window of a few seconds.

**It fails on sustained music, and on any locked-off shot with continuous
movement.** A singer's head moves on phrase shapes rather than onsets; a
close-up of a player's hands never stops moving. Both leave the flux nothing to
key on, and the symptom is a set of answers tens of seconds apart with
correlation margins near zero. Worth one attempt because it costs minutes; not
worth arguing with. Believe the confidence report.

**Repeated takes defeat correlation outright, however good the signal is.** A
recording session is many takes of the same music: the reference contains several
near-identical passages, so a correlator matches a take's audio to a *different
take's* picture and reports a confident, high-scoring, wrong answer. Narrowing
the search window does not rescue it — the window then just clips the peak and
the answer lands on whichever edge it was pushed toward.

This is why a better picture signal does not help. Mouth luminance — an open
mouth is a dark blob, so the darkness of a face region tracks phonation far more
directly than global motion — scores roughly ten times higher than motion flux
and is still not usable here, because what it locks onto is the wrong take. If a
session has repeated takes, go to the hand anchor below rather than spending an
afternoon improving the correlator.

Two implementation traps, if writing something like it:

- **Sampling rate on a slow-motion clip.** To land samples every 1/F of *real*
  time, sample the file at `F / factor` — its own timeline runs `factor` times
  longer than real time. Multiplying instead of dividing stretches the signal by
  factor-squared, and it then correlates with nothing, which reads as "the method
  does not work" rather than as a bug.
- **References with manufactured edges.** Assembling a session-wide envelope by
  pasting take files into a silent background puts a huge step at every take
  boundary, and those steps dominate so completely that unrelated clips all
  "align" to the same one. Correlate against a single continuous recording.

## Verify by looking — arithmetic cannot see a mouth

Never ship on the numbers. The check that settles it costs a minute:

1. Take the **isolated vocal or solo mic, never the mix.** An accompaniment plays
   through the soloist's rests, so "loud moments" taken off the mix put an open
   mouth where a closed one belongs and the test contradicts itself.
2. Find sustained phonation (well above that mic's own median) and true rests.
3. Pull the frame at each and look: mouth open on the sung moments, shut on the
   rests.
4. For frame precision, find the sharpest onset out of silence and step ±5 frames
   through it. The mouth should begin opening at the centre.

A one-second error is glaring under this and invisible under any amount of
arithmetic. It is also sharp enough to choose between two candidate offsets
directly — put them side by side and one of them will fail on a rest.

**It is also slow, and on 2024-05-21 Laurens Leuven it PASSED at an offset that
was 9.4 s wrong** — four sung frames with the mouth open, four silent frames with
it shut, on a placement showing a different moment of the same take. Eight frames
is not eight observations when the singer is phonating most of the time. Treat it
as a last resort and a coarse one, never as the thing that settles a number, and
prefer the disagreement test below, which costs seconds and cannot be flattered.

## Never seek with `ffmpeg -ss` when the answer is a time

**`-ss` before `-i` is a keyframe seek.** It lands where the container lets it,
not where you asked, it reports nothing, and every measurement built on the
extract is then wrong by an amount nobody can see. On that session it moved a
camera offset by **9.4 s**, and a second use of it produced a claim that a camera
was **119 s** out when the real error was 0.58 — both handed over as findings
before the bug was found.

    ffmpeg -ss 550 -i CLIP.MP4 -t 300 -ac 1 -ar 8000 out.wav     # NO
    ffmpeg -i CLIP.MP4 -ac 1 -ar 8000 whole.wav                  # decode once, slice in the analysis

Decode the whole track once and take windows out of the array. A 20-minute clip
is 10 MB at 8 kHz mono, so there is nothing to optimise here. `-ss` *after* `-i`
is accurate but decodes from the start anyway, which is the same cost with a way
to get it wrong.

Why this is in a skill and not a code comment: everything else on this page is
about not believing a correlator. This is about not believing the extract you
handed it, and **a tool that is approximately right and silent about it is worse
than one that fails.**

## Make the takes disagree: the check a margin cannot do

The repeated-takes problem has a cheap answer, and it is not a better statistic.
**Locate every take in the recorder file independently against the whole camera
track, and require them all to imply the same constant offset.** A session with
seven takes of one piece is not seven chances to be fooled; it is seven votes
that have to agree.

Three cameras against the main pair, log envelopes at 25 Hz:

| camera | takes agreeing | spread | |
|---|---|---|---|
| Right_P1000096 | 6 of 7 | 0.042 s | 1.3 frames |
| Front_DJI_0603 | 7 of 7 | 0.029 s | 0.9 frames |
| Keyboard C013 | 7 of 7 | 0.049 s | 1.5 frames |
| Left_DJI_0578 | 0 of 7 | — | **refused** |

**The refusal is what makes the rest believable.** `Left_DJI_0578` does not cover
those takes and its answers disagree by hundreds of seconds. No per-take
threshold would have caught it — its best take scores r 0.767 with a healthy
margin, which passes anything you would set. Only the disagreement catches it.

For contrast, on the same material a single take correlated over the whole file
returned **r 0.851, margin 0.076, and was 9.4 s wrong**, having locked onto a
different take.

Correlate log envelopes, **not waveforms**: `arc pair` over 120 s of a camera mic
against a main pair in a 2.5 s church reads **coherence 0.002**. They share the
shape of the music over time and nothing else.

A working implementation is `~/Projects/arc/migrations/2024-05-21-laurens-leuven/camera-offsets.py`;
arc#260 proposes it as `arc sync`, which is where it belongs.

## An NLE project that already has a sync is half an answer

Check both halves separately, because they fail separately. On that session the
existing Resolve sync timeline had **camera-to-camera offsets good to 0.04–0.10 s**
and the whole group **4.8 s out against the audio** — one shared error, which is
what a take render dropped onto a timeline by hand looks like.

So: take the relative sync from the project, measure the one anchor. Reading the
project wholesale reproduces its error; measuring every camera separately throws
away work someone already did well.

## When nothing automatic works, one hand alignment is enough

Both automated routes can fail on the same session. The fastest way out is to
have whoever can hear it align **one** take by hand, then derive the rest:

    offset = take_start_on_recorder − (camera_clock_at_clip_start + in_point)

**Anchor once per CLIP, not once per session.** Two free-running clocks do hold a
constant difference across an evening, so it is tempting to take one alignment
and apply it everywhere. That fails, because a camera clock that reports whole
seconds quantises every clip's start time independently: each clip inherits up to
±1 s of its own error, and neighbouring clips can disagree by more than a second
even with no drift at all.

The signature is unmistakable once you look for it — corrections agreeing to a
few frames across every take *within* a clip, and jumping by a second or so
*between* clips. So:

- align one take per clip by hand, and propagate that clip's offset to its other
  takes, where it will be right to within a frame or two;
- do not average across clips, and do not trust a single session-wide number;
- a clip with only one take on it still needs its own alignment.

**Always leave picture handles.** Ten seconds of video before the audio and ten
after, on every timeline. Sync gets nudged, and a timeline cut to the exact take
length runs out of frame the moment anyone tries.

## Check what the camera was actually pointed at

Before building anything, look at a frame from **each take's own window**, not
from the middle of the clip. Cameras get repointed between takes, so a clip whose
midpoint shows one thing may be on something else for the take that matters — and
the take someone has chosen on musical grounds is not necessarily the one they
are on camera for.

A contact sheet answers it in one image:

    ffmpeg -ss T -i CLIP.MP4 -vframes 1 -vf "scale=426:240,<log-to-709>" f.png
    ffmpeg -framerate 1 -i "%02d.png" -vf "tile=5x5:padding=6" -frames:v 1 sheet.png

Do this before any editorial decision, and before any offer to build a timeline
around a particular take.
