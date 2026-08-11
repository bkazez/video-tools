---
name: product-video
description: Load BEFORE writing or revising a storyboard for a short product film, demo reel, feature teaser or landing-page video — anything where software or a device is filmed doing something and a viewer has 30 seconds to understand it. Also load when a task mentions a marketing video, a screencast, a demo clip, a storyboard, on-screen titles or captions over a UI, pacing, or a video that "feels slow" or "does not land".
---

# A product film is cut like music, not like a document

A viewer watches a short film the way they listen: what makes 30 seconds feel
fast is not how much happens in it, but how **regularly** it happens. Two
storyboards can show the same six things and only one of them will hold
somebody, and the difference is almost always the grid.

## Beats on a grid, and everything a viewer reads lands on one

Pick a beat between 1.0 s and 1.6 s. Every event a viewer can read or hear — a
title appearing, a stretch of playback starting, a camera move, a keystroke that
changes what is on screen — sits on a multiple of it. Nothing that a viewer
notices happens off the grid.

    beat 1.3 s ->  0.0  1.3  2.6  3.9  5.2  6.5  7.8  9.1  10.4  11.7 …

The mechanics between beats are free, and they have to be: a pointer travelling
to a control, a button going down, the release before a keystroke. Those are how
a beat is *reached*. Only the arrival is on the grid.

**Make the tool enforce it.** A rule in prose gets forgotten by the third
revision. In `arc` the storyboard declares `"beat": 1.3` and the renderer refuses
any title, playback, zoom or keystroke that is off the grid by more than half a
frame, naming the two nearest beats. Put the same check wherever a storyboard is
compiled; a heading 0.3 s late reads as a stumble that nobody can name.

Where the film has real music under it, the beat should be **the music's own
pulse**, not an arbitrary number. Measure it rather than guess it.

## Three steps, each with a title, and no more

The shape that survives contact with a stranger:

1. **A card that names the problem**, one line, on a dimmed frame. Not the
   product, not the company: the thing the viewer already puts up with.
2. **Three steps, numbered, each announced by a big title** over the running
   picture. Not captions at the foot — a caption is read *after* the thing it
   describes, and a viewer who has to work out what they just saw has stopped
   watching. A title is read before, and the action underneath keeps going.
3. **A closing line** that is the promise, not a summary.

Three is the count because a step needs about 4 s to be shown after its title is
read, and four steps do not fit in 30 s with anything left for the last line.

Every title is a verb phrase about what the viewer would do, not a feature name.
"Hear any take from where you point" beats "Audition".

## The demo has to be a real one

Everything below is about honesty, and each one has cost somebody a re-shoot:

- **Drive the real product** through the same input path a hand uses, not a
  mockup and not a hand-held recording. Then a gesture the product does not have
  cannot appear in the film, and the film rebuilds itself when the product
  changes.
- **Choose the material by measurement.** If the film shows an edit, a join, a
  fit or a detection, pick the instance the tool itself scores highest, and say
  the number in the storyboard's comments. A demo of a mediocre example is a
  claim the viewer can hear or see through, and a warning state drawn in orange
  under a caption about clean work is worse than showing nothing.
- **Let the product's own feedback show.** Its toasts, its confidence markers,
  its cursor changes: they read as the software rather than as a video about it.
- **Never speed up or trim the middle of an action.** If it is too slow to show
  in real time, that is a finding about the product.

## Two zooms, not one

Zooming the *content* (a timeline's scale, a map's level) shows more or less of
it. It cannot make a detail drawn in pixels -- a 15 ms crossfade, a button in a
corner -- big enough to look at. That needs a **camera**: magnify the finished
picture, move what you are zooming into toward the middle as you go, and clamp
the move so the frame never shows what is outside the window. Keep the titles out
of the camera or they scale with it and stop being readable.

## Two things to check by eye every time

No assertion covers taste, and these are the two failures that survive a green
build:

- **Does anything move?** A timeline at "fit the whole session" moves a playhead
  a few pixels in 30 s and reads as a still. Zoom in until motion is visible; if
  the wide shot is part of the story, open on it and zoom in on the first beat.
- **Is there dead time at the end?** The last title should land while the last
  action is still resolving, not after it. Cut the film where the story ends,
  not where the storyboard happens to stop.

## Sound

If the product makes sound, the film has sound, and it starts inside the first
second — a viewer who unmutes into silence concludes there is no audio and never
tries again. Aim the programme near -18 LUFS: a landing page that startles is a
landing page people close.

Where the sound is assembled from more than one source, crossfade the joins
rather than butting them (equal-power, 20-25 ms for sustained material), and
render each piece with enough lead-in to have something to fade through.

## On the page

Browsers will not autoplay sound. So: `autoplay muted loop playsinline`, a
poster, and one control that unmutes **where the film already is**. A control
that restarts from the top reads as having done nothing except lose the viewer's
place.

## Worked example

`~/Projects/arc` builds its landing-page film from
`marketing/edit.json` with `bin/make-video`: the app draws every frame,
the engine renders the audio that was playing under each stretch, and the beat
grid, the drag-flag guard and the storyboard's gestures are all checked by the
test suite. `docs/marketing-video.md` there is the method write-up.
