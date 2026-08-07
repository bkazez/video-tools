---
name: colour-grading
description: Load BEFORE grading footage — building a look, fixing a dark or flat picture, deciding a tone curve, or judging whether a grade is working. Also load when a task mentions log footage looking flat, lifted blacks, crushed shadows, grain or noise appearing after a grade, skin tones, a LUT, or applying a grade across a whole project.
---

# Grading from measurements, not from taste alone

A grade argued about in words goes round in circles. A grade with numbers
attached converges, because "too dark" becomes "the subject sits at 26% and
should be at 60-70%". Measure, design a curve against the measurement, verify
the measurement moved, then look.

## Measure the picture first, and say where things sit

Sample frames across the clips that matter, convert them the way the project
will (the log-to-Rec.709 transform, not raw), and take percentiles of luma
0-255 plus the level of the things you care about:

    ffmpeg -ss T -i CLIP -vframes 1 \
      -vf "scale=960:540,format=gbrpf32le,lut3d=<log-to-709>,format=rgb24" \
      -f rawvideo -

Then per frame: `Y = 0.2126R + 0.7152G + 0.0722B`, and report p1 / p50 / p90 /
p99 / peak, plus the median of a background patch and the 92nd percentile of the
subject region.

The numbers that decide the grade:

| what | where it belongs |
|---|---|
| lit skin | 60-70% (150-180 of 255) |
| the top 1% of the frame | 90%+ if anything is meant to read as bright |
| video black | around 16, not 0 — crushing below that throws away shadow detail |

A log conversion LUT deliberately leaves headroom: it is a *starting point*, not
a look. A picture whose peak never exceeds 50% has simply never been graded, and
that is the common case — not an exposure problem.

## Design the curve against those numbers

Interpolate a monotone curve through control points chosen from the measurement —
where black should land, where the subject should land, where the peak should
land — and apply it per channel, then add saturation about the luma:

    y = 0.2126r + 0.7152g + 0.0722b
    out = y + (rgb - y) * SAT          # SAT around 1.10-1.20

Per-channel curves add a little saturation on their own, so keep the explicit
factor modest. Write it out as a `.cube` and verify by re-measuring the same
frames through it.

## The trap: lifting shadows lifts the noise with them

**The local slope of the curve at a level is the noise gain at that level.** A
curve that maps 10/255 to 22/255 has a slope above 2 there and doubles the grain
in everything that dark — which in an interior is most of the frame. It will
measure like a good grade and look like a bad one.

Check it directly: take a flat dark patch, and compare the standard deviation of
its sample-to-sample differences before and after. On one dark-church session,
the first curve took background noise from sigma 0.87 to 1.88 while it took the
subject from 70 to 163. The fix was to hold the bottom of the curve **below** a
slope of 1 and put all the lift in the band the subject occupies — background
ended up darker than the source, noise back to 1.04, subject still at 154.

So: shape the curve so the levels that carry only noise stay flat or fall, and
the levels that carry the subject get the slope.

## What a curve cannot do

**A global curve cannot separate two things that share a luminance.** Black
clothing in a dark room sits at the same level as the wall behind it, so any
curve that brings out the jacket brings out the wall's grain in exactly the same
proportion. There is no control-point arrangement that escapes this.

When that is the limit, the answer is not a better curve:

- **Noise reduction first, then lift.** Temporal NR (Resolve Studio has it)
  removes the grain, after which the shadows can be lifted freely. This is the
  real unlock for a high-ISO interior and it is worth doing before spending more
  time on the curve.
- **A qualifier or mask** to lift the subject without the background.

Say which limit you have hit rather than iterating a curve that cannot get there.

## Applying it across a project in Resolve

`TimelineItem.SetLUT(nodeIndex, lutName)` where the name is relative to the LUT
library. Two things make this fail silently:

- **`Project.RefreshLUTList()` must be called after copying a new `.cube` into
  the library.** Until then Resolve has not scanned it and `SetLUT` just returns
  `False` with no error. This costs an afternoon if you do not know it.
- Re-applying the same LUT **name** after changing the file's contents is how you
  force Resolve to reload it; it caches by name.

Verify with `GetLUT(1)` per clip rather than trusting the return value in bulk.

Keep the `.cube` with the project as well as in the library, so the grade travels
with the session, and name it for the session rather than one piece in it.
