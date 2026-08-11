# video-tools

Tools for the video side of a recording session: reading what a camera actually
recorded, lining footage up with audio from a separate recorder, and building a
DaVinci Resolve project from a spec. Plus the older EDL/OTIO converters this repo
started as (it was `edlutils` until 2026-08).

Everything takes paths as arguments; nothing is specific to one session.

## Camera and sync

| Tool | Answers |
|---|---|
| `bin/sony-clip-info` | what the camera recorded: model, capture frame rate, shutter, ISO, white balance, embedded LUT, wall clock, **slow-motion factor**, silent audio, and **whether focus, zoom or aperture moved mid-take** |
| `bin/camera-session-sync` | the clock offset between a camera and an audio recorder, and which clip covers which take |
| `bin/motion-sync` | the last second of alignment, by correlating picture motion against audio onsets |
| `bin/build-resolve-project` | a whole Resolve project — bins, clip attributes, colour management, timelines — from a YAML spec |
| `bin/frame-noise` | how much noise is really in the picture, per channel — the number that sets a noise-reduction threshold |
| `bin/resolve-copy-grade` | one clip's grade (and its noise reduction) on every other timeline in the project, plus the `.cube` that survives a rebuild |
| `bin/frame-balance` | whether the white in the shot is white, and the per-channel gain that would make it so |
| `bin/build-grade-lut` | a grade as a .cube from control points: white balance, a monotone tone curve, saturation — and the slope table that says what it costs in grain |
| `bin/resolve-set-grade` | that grade applied — a LUT and/or an ASC CDL on node 1 of selected timelines |
| `bin/resolve-audio-check` | whether Resolve's playback is clicking, per page — it is the Color page, and it is 256 samples of digital zero |
| `bin/camera-card-check` | every card you insert, checked against that profile automatically, with a notification — `--install-agent` |

`sony-clip-info --expect` is the pre-shoot check: assert bit depth, chroma, slow
motion, audio, ISO, shutter and `focus: locked` against the card before the day is
spent.
`profiles/` holds worked sets of assertions to copy: `sony-log-video.yml`, and
`sony-4k-cinematic-pal.yml` / `sony-4k-cinematic-ntsc.yml` for 50 Hz and 60 Hz
regions. When there is no time on the day, `camera-card-check --install-agent`
moves the same check to offload, where it costs nothing.

`docs/sony-zv-e10ii-presets.md` is the camera-side half: what to set, why the US
shutter is not 1/48, why focus is a held button rather than a focus mode, and how
to register it so it survives a reset.
`docs/camera-card.html` is the same thing with the reasoning stripped out — open it
on a phone before you roll.

Typical run, from a session folder:

```bash
sony-clip-info Video/                      # is any of this slow motion?
camera-session-sync Video/ Media/ --project "Session.RPP"
build-resolve-project resolve-project.yaml
```

### The two things that make this necessary

**Slow motion invalidates every duration.** A camera in S&Q mode captures at one
rate and writes the file at another, so the container declares a length that is a
multiple of the time the clip really occupies. Nothing in the container says so;
the capture rate is in the camera's own metadata track, which is what
`sony-clip-info` reads. Symptoms are clips that appear to overlap and offsets
that fit nothing.

**Camera audio is often useless.** Sony records none at all in S&Q, so the usual
correlate-the-scratch-audio method has nothing to work with. Both devices do have
clocks, though, and the difference between them is constant over a session —
`camera-session-sync` recovers it by voting on the moments an operator would have
pressed record.

Depth, and the traps worth reading before starting: `skills/camera-sync/SKILL.md`
and `skills/davinci-resolve/SKILL.md`. Both are symlinked into `~/.claude/skills/`.

## Cutting a short product film

`skills/product-video/SKILL.md` is the method for a 30 second demo or teaser:
beats on a regular grid so it reads as music rather than as a list, three
numbered steps with titles over the running picture, choosing the material by
what the tool itself scores highest, and the sound and autoplay rules for a
landing page. `skills/product-video/reference/storyboard.md` beside it is the
file format.

    bin/product-video storyboard.json --frames DIR --out film.mp4 [--audio a.wav]
                      [--backdrop DIR]
    bin/product-video storyboard.json --check
    bin/product-video storyboard.json --layout [--vertical]

`bin/product-video` is the shared half: given a product's bare frames and the
`timeline.json` beside them, it draws the window or the device bezel, flies the
camera, lands the cards and titles and keycaps, muxes the sound, and writes the
mp4 and its poster. It has no idea what the product is, which is the point --
arc's take stack, an iPhone app and a web page come out looking like three films
from one house.

Each product writes only a **frame source**: drive itself through the storyboard,
write `%05d.png` of itself and nothing else, and write the `timeline.json` that
says what shape it drew, what its window is called, where each camera move was
aiming and what it would have been playing. Two are worked: `Arc --movie` in
`~/Projects/arc` fills its own window, and `Wavelength -MOVIE_MODE` in
`~/Projects/wavelength` stands in an iPhone bezel in a room, with `bin/make-video`
in each tying the two halves together.

A product smaller than the picture declares a `canvas` and a `chrome` device, and
`--backdrop DIR` puts footage of the room behind it. `--layout` prints where the
device stands and how big its glass is, in master pixels, because the frame
source needs that rectangle too and one rule beats two.

    bin/device-frame --list          # the bezels there are
    bin/device-frame --json          # the PNG, its screen hole and corner radius

`bin/device-frame` is the one table of where each device's screen sits in its
bezel. `~/bin/frame-shot`, which frames App Store screenshots, reads the same
row, so a still and a frame of the film cannot disagree about where the glass is.

## EDL and OTIO

Older converters, unchanged:

```bash
python3 edl2otio.py --infile file.edl --track 1 --fps 25    # Samplitude EDL -> OTIO
python3 edl2csv.py  --infile file.edl --track 1 --fps 25    # Samplitude EDL -> CSV
python3 otio2edl.py                                         # OTIO -> EDL
python3 csv2cmx3600.py                                      # CSV -> CMX3600 EDL
```

Reaper region → OTIO:

```bash
/Applications/REAPER.app/Contents/MacOS/REAPER "project.rpp" "region_to_otio.lua" -close:nosave:exit
```

Pyramix XML → Reaper multitrack: set the edit cursor in Reaper, run
`apply_pyramix_xml_to_multitrack.lua`, give it the XML path.

## Requirements

`ffmpeg`/`ffprobe` on PATH, `numpy`, `pyyaml`. `build-resolve-project` needs
DaVinci Resolve running with External scripting set to Local.
