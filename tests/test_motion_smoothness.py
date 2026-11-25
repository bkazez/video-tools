#!/usr/bin/env python3
"""motion-smoothness passes an even pan and fails each way a screen recording goes
wrong; retime-recording turns such a recording back into an even pan.

    python3 tests/test_motion_smoothness.py

The picture is random texture sliding down under a white bar held still, as a map
slides under a plane the camera follows.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
CHECK = HERE / "bin" / "motion-smoothness"
RETIME = HERE / "bin" / "retime-recording"
WIDTH, HEIGHT, FPS = 480, 640, 60

failures = []


def check(label, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{'' if ok else '  -- ' + detail}")
    if not ok:
        failures.append(f"{label}: {detail}")


rng = np.random.default_rng(1)
ground = rng.integers(0, 256, (HEIGHT * 8, WIDTH), dtype=np.uint8)
ground = ((ground.astype(float) + np.roll(ground, 1, 0) + np.roll(ground, 1, 1)) / 3).astype(np.uint8)


def picture(position, still=None):
    """The ground `position` pixels along, with the held-still bar over it, and the
    rows outside `still` (first, last) held still too."""
    whole = int(position)
    part = position - whole
    a = ground[whole:whole + HEIGHT].astype(float)
    b = ground[whole + 1:whole + 1 + HEIGHT].astype(float)
    frame = (a * (1 - part) + b * part).astype(np.uint8)
    frame[300:340, 200:280] = 255
    if still:
        frame[:still[0]] = 128
        frame[still[1]:] = 128
    return np.repeat(frame[:, :, None], 3, axis=2)


def write(path, positions, stamps=None, still=None):
    """A video of the ground at these positions: evenly timed, or at the times the ffmpeg
    expression `stamps` gives frame N, on a 1/600 s clock as a simulator's recording is."""
    from PIL import Image
    folder = path.parent
    for index, position in enumerate(positions):
        Image.fromarray(picture(position, still)).save(folder / f"frame{index:05d}.png")
    timing = ["-vf", "setpts=(" + stamps.replace(",", "\\,") + ")/TB", "-fps_mode", "passthrough", "-enc_time_base", "1/600",
              "-video_track_timescale", "600"] if stamps else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(folder / "frame%05d.png"),
                    *timing, "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(path)], check=True)
    for png in folder.glob("frame*.png"):
        png.unlink()


def holds_in(path, positions, fps):
    """The holds motion-smoothness --json finds in a video of POSITIONS at FPS."""
    global FPS
    kept, FPS = FPS, fps
    write(path, positions)
    FPS = kept
    found = json.loads(subprocess.run([sys.executable, str(CHECK), "--json", str(path)],
                                      capture_output=True, text=True).stdout)["faults"]
    return [f for f in found if f["kind"] == "hold"]


def judge(path):
    done = subprocess.run([sys.executable, str(CHECK), str(path)], capture_output=True, text=True)
    return done.returncode, (done.stdout + done.stderr).strip().splitlines()[-1]


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        speed = 3.0                                      # pixels a frame at 60 Hz
        frames = 180

        even = tmp / "even.mp4"
        write(even, [speed * n for n in range(frames)])
        code, said = judge(even)
        check("an even pan is smooth", code == 0, said)

        # A camera easing out of a still and into one again, as product-video moves it:
        # slowing by twice a frame as it lands is a freeze, unless the move is skipped.
        ease = tmp / "ease.mp4"
        write(ease, [0.0] * 30 + [90 * (4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2)
                                  for t in (n / 45 for n in range(46))] + [90.0] * 30)
        done = subprocess.run([sys.executable, str(CHECK), "--skip", f"{30 / FPS}-{75 / FPS}", str(ease)],
                              capture_output=True, text=True)
        check("a camera move it is told to skip is not judged", done.returncode == 0, done.stderr.strip()[-200:])

        # A slow map drawn at half the frame rate: each picture twice. Its steps are too
        # small for the phase correlation to judge, but every other frame is a repeat.
        halved = tmp / "halved.mp4"
        write(halved, [0.2 * (n - n % 2) for n in range(frames)])
        code, said = judge(halved)
        check("a slow picture drawn at half the frame rate is jerky", code == 1 and not said.endswith(" 0 holds"), said)
        slow = tmp / "slow.mp4"
        write(slow, [0.2 * n for n in range(frames)])
        code, said = judge(slow)
        check("and drawn on every frame it is smooth", code == 0, said)

        # Typing: a picture that changes now and then and holds in between is not a stall.
        typed = tmp / "typed.mp4"
        write(typed, [8.0 * (n // 4) for n in range(frames)])
        done = subprocess.run([sys.executable, str(CHECK), str(typed)], capture_output=True, text=True)
        check("a picture that changes every fourth frame has no holds", " 0 holds" in done.stdout + done.stderr,
              (done.stdout + done.stderr).strip()[-200:])

        # A drawer sliding up from rest on a curve that starts steep, as iOS animations do:
        # the first step is the biggest, with nothing moving before it to judge it against.
        onset = tmp / "onset.mp4"
        write(onset, [0.0] * 30 + [60 * (1 - (1 - n / 24) ** 3) for n in range(25)] + [60.0] * 30)
        code, said = judge(onset)
        check("motion starting steeply from rest is smooth", code == 0, said)

        # The simulator: holds a picture for 5 frames, then jumps to where it should be.
        stall = tmp / "stall.mp4"
        positions = [speed * (n - (n % 6 if 60 <= n < 120 else 0)) for n in range(frames)]
        write(stall, positions)
        code, said = judge(stall)
        check("a stall and a catch-up are jerky", code == 1 and "freeze" in said and "jump" in said, said)
        listed = json.loads(subprocess.run([sys.executable, str(CHECK), "--json", str(stall)],
                                           capture_output=True, text=True).stdout)["faults"]
        check("--json lists each fault at its time, inside the stall", listed and
              all(1.0 <= f["at"] <= 2.05 for f in listed), str(listed))
        shots = tmp / "shots"
        done = subprocess.run([sys.executable, str(CHECK), "--frames", str(shots), str(stall)], capture_output=True, text=True)
        printed = [line for line in done.stderr.splitlines() if " into frame " in line]
        pictures = sorted(shots.glob("*.png"))
        check("--frames keeps a picture of each fault it prints",
              len(printed) >= 2 and len(pictures) == len(printed), f"{len(printed)} faults, {len(pictures)} pictures")
        subprocess.run([sys.executable, str(CHECK), "--frames", str(tmp / "none"), str(even)], capture_output=True)
        check("and none of a smooth film", not list((tmp / "none").glob("*.png")))

        # Drawn at 60, kept at 50: a step of one drawn frame, then every fifth a step of two.
        judder = tmp / "judder.mp4"
        write(judder, [speed * (n + n // 5) for n in range(frames)])
        code, said = judge(judder)
        check("60 Hz kept at 50 is jerky", code == 1, said)

        # A room drifting a fifth of a pixel a frame behind a phone, a frame dropped in
        # five: a hitch of a fifth of a pixel nobody can see, not a jerky film.
        drift = tmp / "drift.mp4"
        write(drift, [0.2 * (n + n // 5) for n in range(frames)])
        code, said = judge(drift)
        check("a drift too slow to see judder is not judged", code == 0, said)

        # A phone's recording of an iOS spring: 30 frames a second, the card sliding up on a
        # critically damped curve. Its steps shrink fast, so they say nothing about stalls,
        # but a held frame in the middle of it does.
        def spring(n):
            return 400 * (1 - (1 + n / 4) * np.exp(-n / 4))
        rested = [0.0] * 15 + [spring(n) for n in range(24)] + [spring(24)] * 15
        check("a spring recorded at 30 fps has no holds", holds_in(tmp / "spring.mp4", rested, 30) == [], "")
        stalled = rested[:20] + [rested[20]] * 3 + rested[23:]
        found = holds_in(tmp / "stalled.mp4", stalled, 30)
        check("one held mid-spring for two frames is a hold, at its time",
              len(found) == 1 and found[0]["frames"] == 2 and abs(found[0]["at"] - 21 / 30) < 0.02, str(found))
        # product-video's own camera moves are passed with --skip; a camera eased from rest
        # starts with steps too small to tell from a held frame.
        skipped = json.loads(subprocess.run([sys.executable, str(CHECK), "--json", "--skip", "0.6-1.0",
                                             str(tmp / "stalled.mp4")], capture_output=True, text=True).stdout)["faults"]
        check("a hold inside a --skip span is not judged", [f for f in skipped if f["kind"] == "hold"] == [], str(skipped))

        # A recording: each picture once on time with a copy 2 ms after it, and for the
        # middle second a picture every 50 ms (pictures 60, 63, ... 117).
        positions = [speed * n for n in range(60) for _ in (0, 1)] + \
                    [speed * n for n in range(60, 120, 3) for _ in (0, 1)] + \
                    [speed * n for n in range(120, frames) for _ in (0, 1)]
        copy = "mod(N,2)*0.002"
        stamps = (f"if(lt(N,120), floor(N/2)/60, if(lt(N,160), 1+floor((N-120)/2)*3/60, "
                  f"2+floor((N-160)/2)/60)) + {copy}")
        recording = tmp / "recording.mp4"
        write(recording, positions, stamps)
        code, said = judge(recording)
        check("such a recording is jerky", code == 1, said)
        retimed = tmp / "retimed.mp4"
        done = subprocess.run([sys.executable, str(RETIME), str(recording), str(retimed)],
                              capture_output=True, text=True)
        check("retime-recording runs", done.returncode == 0, done.stderr.strip())
        code, said = judge(retimed)
        check("and makes it smooth", code == 0, said)
        count = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                    "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(retimed)],
                                   capture_output=True, text=True).stdout.strip() or 0)
        check("with every frame the pan had", abs(count - frames) <= 2, f"{count} frames, not {frames}")

        # A stock clip that drops every fifth frame, moving only in a band that starts on
        # an odd row and ends on an even one at full size (analysis blocks 1 to 5), so the
        # moving region's chroma box is a row taller than every other luma row in it.
        stock = tmp / "stock.mp4"
        write(stock, [speed * (n + n // 4) for n in range(frames)], still=(40, 171))
        code, said = judge(stock)
        check("a clip that drops a frame in five is jerky", code == 1, said)
        evened = tmp / "evened.mp4"
        done = subprocess.run([sys.executable, str(RETIME), str(stock), str(evened)], capture_output=True, text=True)
        check("retime-recording runs on a moving region with odd edges",
              done.returncode == 0, done.stderr.strip()[-300:])
        code, said = judge(evened)
        check("and makes it smooth", code == 0, said)

        # A shot held still from its first frame is still as long once retimed.
        held = tmp / "held.mp4"
        write(held, [0.0] * 60)
        kept = tmp / "kept.mp4"
        subprocess.run([sys.executable, str(RETIME), str(held), str(kept)], capture_output=True)
        count = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
                                    "-show_entries", "stream=nb_read_frames", "-of", "csv=p=0", str(kept)],
                                   capture_output=True, text=True).stdout.strip() or 0)
        check("a still shot keeps its length", abs(count - 60) <= 1, f"{count} frames, not 60")

    if failures:
        print(f"\n{len(failures)} failed")
        sys.exit(1)
    print("\nall passed")


if __name__ == "__main__":
    main()
