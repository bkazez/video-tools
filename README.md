# video-tools

Tools for the video side of a recording session: reading what a camera actually
recorded, lining footage up with audio from a separate recorder, and building a
DaVinci Resolve project from a spec. Plus the older EDL/OTIO converters this repo
started as (it was `edlutils` until 2026-08).

Everything takes paths as arguments; nothing is specific to one session.

## Camera and sync

| Tool | Answers |
|---|---|
| `bin/sony-clip-info` | what the camera recorded: model, capture frame rate, shutter, ISO, white balance, embedded LUT, wall clock, **slow-motion factor**, silent audio |
| `bin/camera-session-sync` | the clock offset between a camera and an audio recorder, and which clip covers which take |
| `bin/motion-sync` | the last second of alignment, by correlating picture motion against audio onsets |
| `bin/build-resolve-project` | a whole Resolve project — bins, clip attributes, colour management, timelines — from a YAML spec |
| `bin/frame-noise` | how much noise is really in the picture, per channel — the number that sets a noise-reduction threshold |
| `bin/resolve-copy-grade` | one clip's grade (and its noise reduction) on every other timeline in the project, plus the `.cube` that survives a rebuild |
| `bin/frame-balance` | whether the white in the shot is white, and the per-channel gain that would make it so |
| `bin/build-grade-lut` | a grade as a .cube from control points: white balance, a monotone tone curve, saturation — and the slope table that says what it costs in grain |
| `bin/resolve-set-grade` | that grade applied — a LUT and/or an ASC CDL on node 1 of selected timelines |

`sony-clip-info --expect` is the pre-shoot check: assert bit depth, chroma, slow
motion, audio, ISO and shutter against the card before the day is spent.
`profiles/sony-log-video.yml` is a worked set of assertions to copy.

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
