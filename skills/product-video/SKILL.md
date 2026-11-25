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

**A run of the same action accelerates through the subdivisions.** Two a beat
apart, then two at the half, then four at the quarter, then four at the eighth:
quarters into eighths into sixteenths into thirty-seconds. It is the one figure
that builds energy without anything else changing, and a film that has it once
has a shape -- a stretch of even presses at any speed reads as a list. Keep the
run inside the grid, which is what the subdivision is for, and let it end on
whatever the product should be left showing rather than wherever the count
happened to stop.

**Make the tool enforce it.** A rule in prose gets forgotten by the third
revision. In `arc` the storyboard declares `"beat": 1.3` and the renderer refuses
any title, playback, zoom or keystroke that is off the grid by more than half a
frame, naming the two nearest beats. Put the same check wherever a storyboard is
compiled; a heading 0.3 s late reads as a stumble that nobody can name.

Where the film has real music under it, the beat should be **the music's own
pulse**, not an arbitrary number. Measure it rather than guess it.

## The picture explains it; the first two seconds stop the scroll

No titles by default. A viewer looks at a phone doing something; words on top
of it read as an ad, and an ad is the thing people have learned not to look at.
Numbered steps, a card naming the problem, a promise in big type: all of them
are promotion, and they push the product out of the frame they sit on.

1. **Open on the most arresting moment the product has**, in the first two
   seconds, before anything is explained: the plane sweeping across the map,
   the trip appearing, the sound starting. Not a home screen, not typing, not
   a setup. A viewer decides in those two seconds whether to keep watching.
2. **Let each action explain itself.** Choose and order the moments so a
   stranger can follow them with the sound off: the tap, then what it found,
   held long enough to see. If a moment cannot be understood without words,
   first try a better moment.
3. **A title only where the picture truly cannot carry it**, one or two in a
   film at most: short, plain, a fact about what is on screen ("50 minutes
   late from Dallas"), never a slogan or a pitch. A platform that plays muted
   in a feed does not change this; the arresting opening is what carries it.

**The words are the owner's, and they are used exactly.** When Ben writes a
title, it goes in the film character for character. A title that reads better
is not license to reword one. Add no line he did not write.

**A title lands, it does not fade.** Opaque in about 0.07 s, a tenth over size
on arrival, settling over 0.16 s. A linear fade reads as hesitation.

## The demo has to be a real one

Everything below is about honesty, and each one has cost somebody a re-shoot:

- **Film the version people can get today.** Build from the commit of the
  newest released build (its `ios-<version>-<build>` tag), never from `main`.
  A film of features the store does not have yet promises what a buyer cannot
  get.
- **It is a real video, smooth at the display's frame rate.** A simulator
  recording drops and repeats frames, so a scroll or a waveform judders like a
  GIF. Record on a physical device's screen capture, and ship only a film
  `bin/motion-smoothness film.mp4` passes.
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
- **Type fast; hold on the idea.** Typing goes in a letter at a time, fast
  (`typeByHand` in visual-test-tools' Filming), and only as much as the search
  needs to find the thing: the viewer
  waits for what the typing finds, not for the letters. Spend the time saved on
  a hold after the moment that shows something new, long enough to grasp it.
- **Leave out the app's housekeeping.** A row or prompt asking for a permission
  is the app's business, not the film's. Refuse the permission on the filming
  simulator (`xcrun simctl privacy SIM revoke contacts BUNDLE_ID`) so it never
  shows.
- **Never speed up or trim the middle of an action.** If it is too slow to show
  in real time, that is a finding about the product.

## A story first, told by the camera

Write the story before a single event: one person, what they want, what is in
their way, and how the product gets them there, as one sentence per beat. A
tour of features is not a story, and a camera cannot rescue one. The picture
tells the story, and the camera tells it the way Roger Deakins shoots:
the audience should feel every move and notice none.

- **Every move is motivated by the story.** It goes where a person in that
  scene would look at that moment: in as the reading arrives, out when the
  room or the trip is what matters. Give each camera event a `"why"` naming
  the beat it serves. Read only the `why` lines, in order: they should retell
  the story. A move whose why is "variety" or "energy" comes out.
- **Stillness is the default.** Most shots hold or drift slowly; a move is
  earned by a change in the story, such as a discovery, a decision or an
  arrival. Restraint is what makes the one push that matters land.
- **The camera has its own arc.** Open wide enough to establish where we are,
  come closer as the stakes rise, and give the resolution and the end card
  room to breathe. Do not reset to wide between beats out of habit.
- **Gentle numbers.** For a device in its world, stay at 1.3x or under unless
  a detail cannot be read otherwise. No move under 1.5 s. Never go in and back
  out within one beat, and never reverse direction without a cut between.
  Twelve pushes in 30 s between 1.0x and 2.6x read as zooming in and out of
  the phone (Wavelength's site film before b7f1b28).
- **Cut rather than whip.** When the story jumps to another place or time,
  cut, and land the cut with the camera already easing in the direction the
  next beat needs.

Check by eye at full speed with the sound off: could a stranger retell the
story, and did they notice the camera? If they noticed it, it is too much.

## Two zooms, not one

Zooming the *content* (a timeline's scale, a map's level) shows more or less of
it. It cannot make a detail drawn in pixels -- a 15 ms crossfade, a button in a
corner -- big enough to look at. That needs a **camera**: magnify the finished
picture, move what you are zooming into toward the middle as you go, and clamp
the move so the frame never shows what is outside the window. Keep the titles out
of the camera or they scale with it and stop being readable. The camera's
moves follow the story (above), not the grid alone.

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

An app's page opens on its phone: the film cut to the phone alone, in its
frame on black with no words, standing on the right, and the app's name or
slogan with the download button on the left (impulsearc.com/legato). Every
pipeline that films an app writes this phone-only cut beside its reels. Only
a camera app (Wavelength) runs its film full bleed, because the film has to
show the scene the camera sees; then no headline goes over it, and it is no
taller than the viewport minus the room the download button needs.

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
