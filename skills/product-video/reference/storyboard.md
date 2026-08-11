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
| `chrome` | draw the platform's window or device frame around it |
| `vertical` | the same film redrawn in this shape, for a phone |
| `target_lufs` | where the finished sound is aimed; -18 for a landing page |
| `poster_at` | which second becomes the still |

## Events

Each event has `at` (seconds of video) and one action. Everything a viewer reads
or hears must land on the beat; the mechanics between beats are free.

| Action | Meaning |
|---|---|
| `"do": "STEP"` | one gesture, in the product's own script grammar |
| `"card": "…", "seconds": N` | a line over a dimmed frame; `"then": {"text": "…", "at": S}` adds a second line under it, laid out from the start so the first does not jump |
| `"step": "…", "seconds": N` | a big centred title over the running picture; the numbering is part of the string |
| `"play": {"from": S, "seconds": N, "solo": "…"}` | the product plays from second S of its own material; this is also how the film seeks |
| `"glide": "WHERE", "seconds": N, "dragging": true` | the pointer travels; `dragging` when a button is down |
| `"zoom": {"to": X, "at": "WHERE", "seconds": N}` | the **content's** own scale |
| `"camera": {"to": X, "at": "WHERE", "seconds": N}` | the **picture** magnified, panning what it zooms into toward the middle |

`WHERE` is the product's own way of naming a place — in arc, `lane12@114.7` is a
take and a second, `autoedit` is a button. **Never a raw coordinate where a name
exists**: a name survives a window resize and a layout change, and a coordinate
silently aims at the wrong thing.

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

## Refusals a frame source owes you

Each of these was a real defect that shipped or nearly shipped:

- **A gesture the product does not have** must fail the build, not draw a frame.
- **A drag whose glide forgot `"dragging"`** moves the pointer and leaves the
  selection behind, so the next Return places nothing: 780 frames of an edit that
  never happened, every one of them looking fine.
- **An audition the storyboard did not declare**: ask the product every frame what
  it is playing, and refuse where that is not what the sound track will play.
- **A title off the beat**, by more than half a frame.
