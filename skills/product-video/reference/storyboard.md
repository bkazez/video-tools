# The storyboard grammar

One JSON file is the whole film: what happens, when, and in what words. Two
things read it — a **frame source** that knows how to drive one product, and the
**assembler** that turns frames into an mp4. Every product implements the first;
nothing reimplements the second, and nothing reimplements the look.

The reference implementation is `~/Projects/arc`: `app/Arc/Movie.swift` is a
frame source, `bin/make-video` is the assembler, `marketing/edit.json` is a
storyboard. Read those before writing a second one.

## The file

```json
{
  "width": 1440, "height": 810, "fps": 30, "scale": 2,
  "seconds": 27, "beat": 1.0, "subdivide": 2,
  "chrome": true,
  "vertical": {"width": 760, "height": 1240},
  "target_lufs": -18, "poster_at": 4.0,
  "events": [ … ]
}
```

| Key | What it is |
|---|---|
| `width`/`height` | the product's own drawing area, in points, before `chrome` |
| `scale` | render at this multiple for a crisp master; 2 is right |
| `beat` / `subdivide` | the grid every title, sound and keystroke lands on; 8 lets a run of keystrokes accelerate from quarters to thirty-seconds and stay in tempo |
| `chrome` | `"macos"` for the platform's window, or a device `bin/device-frame --list` knows (`"iphone-16-pro-max"`) for a bezel. `true` still means the platform's window. A product wider than tall (`"width": 956, "height": 440`, an app that runs sideways) stands in the bezel turned a quarter left, Dynamic Island on the left, and `ui-test-film` turns the simulator's upright recording to match |
| `canvas` | `{"width": …, "height": …}` — the film's frame, when it is bigger than the product. A phone stands in a room; the room is the rest of the canvas. Omit it and the product is the picture, which is what a window-filling product wants |
| `device_fill` | how much of the canvas a bezel stands in, 0.72 by default to leave room for titles; a film with no words gives it 0.94 |
| `background` | `"#03070F"` — the canvas behind the product where there is no `--backdrop` |
| `vertical` | the same film redrawn in this shape, for a phone; it overrides any of the keys above |
| `wide`, `feed`, `vertical`, `phone`, `preview` | built in for every device film, so every app has the same set: 16:9 (`wide`, 960x540 points) and 4:5 (`feed`, 540x675) for a feed, 9:16 (`vertical`, 540x960) for a reel, the bezel alone on black with no titles and no camera for a web page (`phone`), and the screen alone for the App Store (`preview`). `ui-test-film --all DIR --marcom PRODUCT` cuts all five from one recording, names each by its Marcom asset type, and files them in Marcom. A storyboard's block of the same name overrides any of their keys. Any variant block may also say `"canvas": "device"`, `"words": false`, `"camera": false`, `"background"` and `"device_fill"` |
| `target_lufs` | where the finished sound is aimed; -18 for a landing page |
| `poster_at` | which second becomes the still |
| `before` | `["search SFO to ORD", "open UA 2296"]` — gestures played unfilmed before the recording rolls, so the film opens on the product's most arresting moment rather than its first screen (Filming's `playFilm`, which waits its `settle` seconds after them) |

## Events

A film with no words has `"events": []`. Each event has `at` (seconds of video) and one action. Everything a viewer reads
or hears must land on the beat; the mechanics between beats are free.

| Action | Meaning |
|---|---|
| `"do": "STEP"` | one gesture, in the product's own script grammar; `"keycap": false` beside it keeps a keystroke off the screen |
| `"card": "…", "seconds": N` | a line over a dimmed frame; `"then": {"text": "…", "at": S}` adds a second line under it, laid out from the start so the first does not jump |
| `"step": "…", "seconds": N` | a big centred title over the running picture; the numbering is part of the string |
| `"play": {"from": S, "seconds": N, "solo": "…"}` | the product plays from second S of its own material; this is also how the film seeks |
| `"glide": "WHERE", "seconds": N, "dragging": true` | the pointer travels; `dragging` when a button is down |
| `"zoom": {"to": X, "at": "WHERE", "seconds": N}` | the **content's** own scale |
| `"camera": {"to": X, "at": "WHERE", "seconds": N}` | the **picture** magnified, panning what it zooms into toward the middle |

`WHERE` is the product's own way of naming a place — in arc, `lane12@114.7` is a
take and a second, `autoedit` is a button; in Wavelength, `meter` and `itinerary`
are regions the views claim for themselves. **Never a raw coordinate where a name
exists**: a name survives a window resize and a layout change, and a coordinate
silently aims at the wrong thing.

A product may add a verb of its own for the thing its film is about — Wavelength
has `"scene": {…}`, one stretch of film in one light, in one room, at one moment.
Anything that changes the picture is on the beat with the words, because a cut is
as loud as a title.

## A product that stands in a room

A device bezel and a canvas bigger than the product bring one more input: the
room. `--backdrop DIR` is a PNG sequence, one frame per frame of film, drawn
behind the device and travelling with it under the camera.

They must already be the canvas's exact pixel size, and the tool refuses them
otherwise. That is not fussiness: the same footage is what the *product* is
looking at — Wavelength crops each backdrop frame to the glass and hands it to
the app as the camera feed, so the phone reads as transparent — and it can only
be the same pixels if nobody is scaling them twice.

Where the device stands is the film's decision, not the product's, so it lives
here and the product asks:

    product-video storyboard.json --layout [--vertical]
    {"canvas":{"height":1080,"width":1920},"scale":2,
     "screen":{"height":743,"width":342,"x":789,"y":168}}

in master pixels, top-left origin, ready for an ffmpeg crop. Two copies of
"centred at 72% of the height" would drift apart on the first change.

## What a frame source has to do

For each frame at `t = i / fps`:

1. fire every event due at or before `t`, in order;
2. advance whatever is continuous (a pointer gliding, a zoom, a playhead);
3. draw the product, and only the product;
4. write `%05d.png`.

And then write `timeline.json`:

```json
{"fps": 30, "frames": 810, "seconds": 27, "width": …, "height": …, "scale": 2,
 "audio": [{"from": 0.0, "to": 5.0, "source": …, "from_source": 104.0, "to_source": 109.0}]}
```

`audio` is the film's honest account of what the product would have been playing
over each stretch of video: one entry per stretch, closed whenever what is
playing changes, **including on every seek**. The assembler renders each entry
through the product and crossfades the joins. Silence is an entry that renders
nothing; a film that hides a real silence is lying about the product.

## A product that cannot draw itself one frame at a time

MapKit, SwiftUI springs and UIKit transitions run on the wall clock, so an app
built of them cannot be stepped a frame at a time: a snapshot per frame shows
its animations in jumps. Its UI test is the frame source instead. It plays each `"do"` after the last one has landed, and aims
each `"camera"` at the element the screen calls that name (an accessibility
identifier, or a label), once it has stopped sliding:

```swift
import Filming

try playFilm(in: app, settle: 8, lead: { _ in 0.3 }) { step in   // a press lands as it lifts
    switch step {
    case "back": pressByHand(app.buttons["back"], after: 0)
    default: XCTFail("no gesture \"\(step)\"")
    }
}
```

A gesture takes a loaded simulator one to three seconds, so `bin/ui-test-film`
cuts the recording rather than playing it in real time: each stretch starts at
a gesture's touch, the still moment before it is dropped, and every gesture
lands on its beat. Nothing inside an action is cut or sped up. The camera's
timing is the storyboard's, so changing a move recuts without a new recording.
FlightTrack is the worked example: `ios/FlightsUITests/ProductFilmTests.swift`,
`ios/bin/make-video`, `marketing/edit.json`.

## Refusals a frame source owes you

Each of these was a real defect that shipped or nearly shipped:

- **A gesture the product does not have** must fail the build, not draw a frame.
- **A drag whose glide forgot `"dragging"`** moves the pointer and leaves the
  selection behind, so the next Return places nothing: 780 frames of an edit that
  never happened, every one of them looking fine.
- **An audition the storyboard did not declare**: ask the product every frame what
  it is playing, and refuse where that is not what the sound track will play.
- **A title off the beat**, by more than half a frame.
