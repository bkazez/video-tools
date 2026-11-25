# video-tools

Tools for the video side of a recording session: reading what a camera actually
recorded, lining footage up with audio from a separate recorder, and building a
DaVinci Resolve project from a spec. Plus the older EDL/OTIO converters this repo
started as (it was `edlutils` until 2026-08).

Everything takes paths as arguments; nothing is specific to one session.

The skills in `skills/` (product-video, camera-sync, colour-grading,
davinci-resolve) reach Claude on a machine once it runs:

    bin/install      # links each skill into ~/.claude/skills

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
| `bin/resolve-conform` | every video timeline put back in sync with an arc mix that has been re-comped, working out from arc's own document what moved and by how much |
| `bin/resolve-ripple` | time inserted or taken out at a point you name, when there is no arc document to read — the manual half of the same machinery |
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
on a phone before you roll. `docs/focus-card.pdf` is the focus setup alone as a 3×5
index card to print and keep in the bag; edit `docs/focus-card.html` and re-render
it with `bin/html-to-pdf docs/focus-card.html`.

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
                      [--backdrop DIR] [--loop]
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

An app made of MapKit, SwiftUI springs and UIKit transitions cannot draw itself
one frame at a time: those run on the wall clock. There the UI test is the frame
source. It plays the storyboard's gestures (visual-test-tools' Filming,
`playFilm`), the simulator records it (`sim-film`), and `bin/ui-test-film` cuts the
recording so each gesture lands on its beat and hands it to `product-video`. FlightTrack
is the worked one (`ios/bin/make-video` in `~/Projects/flighttrack`).

    simq run -- bin/ui-test-film edit.json --project App.xcodeproj --scheme App \
        --test AppUITests/ProductFilmTests/testTheProductFilm --out film.mp4
    bin/ui-test-film edit.json --recording /tmp/ui-test-film-film/recording.mp4 --out film.mp4

A product smaller than the picture declares a `canvas` and a `chrome` device, and
`--backdrop DIR` puts footage of the room behind it. `--layout` prints where the
device stands and how big its glass is, in master pixels, because the frame
source needs that rectangle too and one rule beats two.

    bin/device-frame --list          # the bezels there are
    bin/device-frame --json          # the PNG, its screen hole and corner radius

`bin/device-frame` is the one table of where each device's screen sits in its
bezel. `~/bin/frame-shot`, which frames App Store screenshots, reads the same
row, so a still and a frame of the film cannot disagree about where the glass is.

### No film leaves jerky

    bin/motion-smoothness film.mp4               # exit 1 on a freeze, a jump or an uneven cadence
    bin/motion-smoothness --loop loop.mp4        # and the last frame into the first
    bin/motion-smoothness --frames out/ rec.mp4  # each fault as one PNG: the frame before beside the frame after
    bin/retime-recording recording.mp4 even.mp4 --from 32.5 --seconds 42 --fps 60
    bin/film-until-smooth -- bin/make-video      # record again while product-video says jerky (exit 3), 3 tries

`motion-smoothness` measures how far the moving part of the picture goes each
frame (block phase correlation, `lib/motion.py`) and fails a step far from its
neighbours'. `product-video` runs it on every film and deletes one that fails.
FlightTrack's iPad 4:5 Follow Mode cut, which Ben called jerky, fails it (122
freezes and 124 jumps in 864 frames); so does the iPhone one he called better
(293 freezes and 215 jumps in 1384: a double step every fifth frame, from 60 Hz
kept at 50, and every few seconds a stretch the app drew at 20 Hz).

A freeze or a jump in a recording of an app is the app's fault, never the
recorder's: fix the app, and measure the same motion on an iPhone
(visual-test-tools `bin/hitches`) before calling it smooth.

`retime-recording` makes a film from a recording: each picture drawn once, as
many frames at `--fps` as the picture moved, and the frames between built from
the two either side, moving only what moved. It hides stalls, so it never
judges an app.
`tests/test_motion_smoothness.py` proves both directions on a synthetic pan.

### No app's own animation stutters

    bin/app-smoothness                       # the app checked out here, on the iPhone: exit 1 on a stutter
    bin/app-smoothness --frames /tmp/s       # and each stutter as the frame before beside the frame after
    bin/app-smoothness --recording rec.mp4   # judge a recording made already (rec.xcresult beside it)

It plays the app's `AppReviewDemoTests` on homebase's iPhone (visual-test-tools
`device-demo`, holding the phone with `iphone`) and runs `motion-smoothness` over
the whole recording, with nothing skipped after a touch. Each stutter is printed
with the test's last action before it:

    app-smoothness: JERKY flighttrack on iPhone 12 mini iOS 27.2, 88.8 s; 6 stutters
      hold   at   11.07 s   1 frame late while the picture moves    1.11 s after Tap "flight-result" Button

A stutter is a hold: a frame late while the picture moves. The phone records 30
pictures a second and stores one only when the screen changes, so a late frame is
a gap. The step-against-neighbours faults are not counted: a smooth iOS spring at
30 fps fails them on its own (`tests/test_motion_smoothness.py`, "a spring
recorded at 30 fps").

It finds the project, scheme and UI-test target from the test file, so every app is
checked the same way. No model is called.

Every TestFlight build runs it on the commit it uploaded, as the last step of
agent-ops' [`mac.yml`](https://github.com/bkazez/agent-ops/blob/main/.github/workflows/mac.yml)
("Animations on the iPhone"). A stutter, or a demo test that does not play to its
end, turns the build red; the upload has already happened. An app without the
test, or a phone that is not ready, gets a warning on the run instead.

## Conforming picture to a mix that changed length

A mix is re-comped — a join moves, a take runs longer, a passage becomes one
take through — and every video timeline cut against the old render is out of
sync. The question a person cannot answer from a waveform, and arc can answer
exactly, is *where* and *by how much*.

```bash
resolve-conform "Polyphemus mix.arc" --since HEAD~1 --dry-run
resolve-conform "Polyphemus mix.arc" --since HEAD~1
```

**It is not one number, and that is the whole point.** arc's document says, per
item, `at` (where it sits in the mix) and `soffs` (where it starts in its take);
the difference is that take's own clock against the mix, and the clock is what
the picture follows. On the 2026-08-27 Polyphemus re-comp the mix grew exactly
1.000 s while the take at the join started 0.181 s earlier in its own source —
items 0–7 had a clock delta of 0 and items 8–30 had 1.000. A single ripple would
have been wrong at the join and right nowhere it mattered.

So each clip is moved by the delta of the take it is showing:

| clip | what happens |
|---|---|
| a camera clip | **shifts** by the delta of the arc item it spends most of its time over, keeping its length — its own cuts are somebody's edit |
| the mix, and full-length overlays | **stretch**: the start moves by the delta where they start, the end by the delta where they end |
| two clips that used to meet | the first is **lengthened out of its own source** to still meet the second |

That last row is where the extra second of picture comes from, instead of a hole
somebody has to fill. A gap opening where the clips did **not** meet before is an
overlay track's own spacing, and is left alone.

`--since` is the revision the timelines were last cut against — the recording
project is in git, so a sha, a tag, or `HEAD~1`. **Get it right**: run from a
revision that already contains part of the change and everything before it is
silently never applied, and every check here still passes, because they all ask
whether the timeline matches the plan rather than whether the plan was right.
Where the video was cut to a REAPER edit, the baseline is the commit that
imported it. `--until` conforms to a revision rather than to the working tree,
which is how a run from the wrong baseline is corrected without undoing it.

**A re-comp can delete a piece of the edit, and no move fixes that.** Where the
picture is cut over an item that is gone, it is showing a take that is not in
the mix any more — reported as `ORPHAN`, with the take that took its place.
`--recut-orphans` runs the clip before it on through, when that clip is the take
you now hear; it removes a cut somebody made, so it is a flag and not a default.

### The round trip underneath, and why it is DRT

Resolve cannot move a clip by script: `TimelineItem` has no `SetStart`. So the
edit leaves as a file and comes back, and which file decides whether the grades
survive. Measured 2026-08-27 on `Polyphemus Horizontal` (83 items, 3-node
grades, a 3.16× vertical reframe):

| round trip | cuts | grades | reframes | picture |
|---|---|---|---|---|
| OTIO | 70/70 | 31/70 | 49/70 | mean 37.8–91.0 off |
| DRT | 83/83 | 83/83 | 83/83 | mean 3.25 off, against a 3.2 same-frame-twice floor |

DRT is Resolve's own timeline format rather than an interchange one, so a grade
and a reframe have somewhere to go. Every run re-checks that on its own
material: it compares the imported timeline against the plan it made, then
renders matched frames out of both timelines against a floor measured from the
still exporter's own repeatability — and beside each one a frame a second away,
so a point that cannot tell two pictures apart is reported as having proved
nothing rather than counted as a pass. A timeline that fails is left beside the
original as `… (UNVERIFIED)` and the original is not touched.

### When there is no document to read

`bin/resolve-ripple` is the same machinery driven by hand — a point and an
amount you supply — for a timeline whose audio is not an arc project:

```bash
resolve-ripple --media "soundtrack.wav" --at 1:07.8 --by 1s --dry-run
resolve-ripple --timeline "WDN Edit" --at 00:01:06:20 --by -25f
```

With `--media`, `--at` is a point in the media's own time and each timeline's
position is worked out from its own offset into it. A clip the point falls
inside is the one case with no right default: `--straddle split` (default) cuts
it and leaves a real hole, `repeat` covers the hole with the shot running on,
`extend` lets it run longer. Stills always extend. `--by -N` at the point `--by
+N` was given undoes it exactly, closing the cut it made.

`lib/drt.py` is the file format on its own, `lib/resolve.py` the Resolve side,
and `tests/test_drt.py`, `tests/test_resolve_ripple.py` and
`tests/test_conform.py` exercise all three without Resolve running.

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

`ffmpeg`/`ffprobe` on PATH, `numpy`, `pyyaml`, and `pillow` for
the picture checks. `build-resolve-project` and the other `resolve-*` tools need
DaVinci Resolve running with External scripting set to Local; `resolve-conform`
also needs `arc` on the path and the recording project in git.
