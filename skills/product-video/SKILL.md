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

## A card, then numbered steps, and nothing else on screen

The shape that survives contact with a stranger:

1. **A card that names the problem**, on a dimmed frame. Not the product, not the
   company: the thing the viewer already puts up with. A second line can land
   under the first while it is still up — the answer to it, not a replacement.
2. **Numbered steps, each announced by a big centred title** over the running
   picture. Not captions at the foot — a caption is read *after* the thing it
   describes, and a viewer who has to work out what they just saw has stopped
   watching. A title is read before, and the action underneath keeps going.
3. Three to five steps. A step needs about 4 s after its title is read.

Every title is a verb phrase about what the viewer would do, not a feature name.
"Hear any take from where you point" beats "Audition".

**The words are the owner's, and they are used exactly.** When Ben writes the
titles, they go in the film character for character, numbering included. A title
that reads better is not licence to reword one, and the number belongs *in* the
string rather than drawn beside it as a mark of your own — that quietly turns
"1. Arc automatically aligns your takes" into two different things in two places.
Add no sixth line he did not write.

**Titles land, they do not fade.** Opaque in about 0.07 s, a tenth over size on
arrival, settling over 0.16 s. A linear fade reads as hesitation, and hesitation
is the opposite of what a film cut to a beat is doing.

## The demo has to be a real one

Everything below is about honesty, and each one has cost somebody a re-shoot:

- **Drive the real product** through the same input path a hand uses, not a
  mockup and not a hand-held recording. Then a gesture the product does not have
  cannot appear in the film, and the film rebuilds itself when the product
  changes.
- **Show the window it lives in.** A rectangle of interface with nothing around
  it reads as a diagram; a title bar with its three lights, or a device frame,
  reads as software somebody is using. Take the title on that bar from the
  product's own code rather than typing one in.
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

**It is the product's own sound, in the order the film plays it.** Not a bed, not
a library track: what the product would have been playing over that stretch of
video, seeks included. A stretch ends whenever what is playing changes and
whenever the film seeks, or one continuous piece of sound ends up under a picture
that jumped. Where the sound is assembled from more than one stretch, crossfade
the joins (equal-power, 20-25 ms for sustained material) and render each stretch
with enough lead-in to have something to fade through.

**A real silence stays.** If the product goes quiet while somebody sets something
up, so does the film.

## A phone gets the film redrawn, not cropped

A 9:16 crop of a wide interface is a sliver of it. Redraw the same storyboard in
a tall shape instead: same gestures, same words, same music, and the layout of
the product does the rest. It costs nothing when every gesture aims at a name the
product resolves rather than at a coordinate. Titles wrap and size themselves to
the frame they are in.

## On the page

The page has one job. No headline over the film — a line of type above it only
pushes it down; keep the heading in the document for a screen reader and search
and do not draw it. Full bleed, and no taller than the viewport minus the room
the call to action needs, so the film and the way to sign up are on screen
together.

Browsers will not autoplay sound. So: `autoplay muted loop playsinline`, a
poster, and one control that unmutes **where the film already is**. A control
that restarts from the top reads as having done nothing except lose the viewer's
place. Pick the wide or tall file with one `matchMedia` before playback starts,
so only one of them is ever downloaded.

## The storyboard, and how a second product joins

`reference/storyboard.md` in this skill is the grammar: one JSON file per film,
read by a **frame source** that knows how to drive one product and by
`bin/product-video` here, which turns frames and a timeline into a film. A new
product writes the frame source and nothing else -- the window, the camera, the
words, the sound and the poster are already written and are the same for every
product, which is what makes them look like one house.

`~/Projects/arc` is the worked example and the reference implementation:
`app/Arc/Movie.swift` is its frame source, `bin/make-video` the assembler,
`marketing/edit.json` the storyboard, `docs/marketing-video.md` the write-up, and
`tests/test_movie.py` checks the beat grid, the refusals and every gesture in the
shipped storyboard. Read those four before starting a second film.
