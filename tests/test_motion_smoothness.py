#!/usr/bin/env python3
"""motion-smoothness passes an even pan and fails each way a screen recording goes
wrong; retime-recording turns such a recording back into an even pan.

    python3 tests/test_motion_smoothness.py

The picture is random texture sliding down under a white bar held still, as a map
slides under a plane the camera follows.
"""
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


def picture(position):
    """The ground `position` pixels along, with the held-still bar over it."""
    whole = int(position)
    part = position - whole
    a = ground[whole:whole + HEIGHT].astype(float)
    b = ground[whole + 1:whole + 1 + HEIGHT].astype(float)
    frame = (a * (1 - part) + b * part).astype(np.uint8)
    frame[300:340, 200:280] = 255
    return np.repeat(frame[:, :, None], 3, axis=2)


def write(path, positions, stamps=None):
    """A video of the ground at these positions: evenly timed, or at the times the ffmpeg
    expression `stamps` gives frame N, on a 1/600 s clock as a simulator's recording is."""
    from PIL import Image
    folder = path.parent
    for index, position in enumerate(positions):
        Image.fromarray(picture(position)).save(folder / f"frame{index:05d}.png")
    timing = ["-vf", "setpts=(" + stamps.replace(",", "\\,") + ")/TB", "-fps_mode", "passthrough", "-enc_time_base", "1/600",
              "-video_track_timescale", "600"] if stamps else []
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(folder / "frame%05d.png"),
                    *timing, "-c:v", "libx264", "-qp", "0", "-pix_fmt", "yuv420p", str(path)], check=True)
    for png in folder.glob("frame*.png"):
        png.unlink()


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

        # The simulator: holds a picture for 5 frames, then jumps to where it should be.
        stall = tmp / "stall.mp4"
        positions = [speed * (n - (n % 6 if 60 <= n < 120 else 0)) for n in range(frames)]
        write(stall, positions)
        code, said = judge(stall)
        check("a stall and a catch-up are jerky", code == 1 and "freeze" in said and "jump" in said, said)

        # Drawn at 60, kept at 50: a step of one drawn frame, then every fifth a step of two.
        judder = tmp / "judder.mp4"
        write(judder, [speed * (n + n // 5) for n in range(frames)])
        code, said = judge(judder)
        check("60 Hz kept at 50 is jerky", code == 1, said)

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

    if failures:
        print(f"\n{len(failures)} failed")
        sys.exit(1)
    print("\nall passed")


if __name__ == "__main__":
    main()
