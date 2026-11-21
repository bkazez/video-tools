"""How the picture moves from one frame to the next: shared by motion-smoothness,
which judges it, and retime-recording, which evens it out.

The picture is cut into blocks, and each block is phase-correlated with the same
block of the next frame. That handles what a single whole-frame correlation does
not: a map pitched in perspective, a slow turn, and a card, a status bar or a plane
held still on top of the motion, which would otherwise pull the answer to zero.
Only blocks that change over the video are used.
"""
import json
import subprocess

import numpy as np

WIDTH = 1080             # analysis width
BLOCK = 64               # block side, analysis pixels
CHANGING = 4.0           # a pixel whose grey varies this much over the video is moving
PEAK = 0.15              # a correlation peak under this has no counterpart: a cut, not a move
_WINDOW = np.outer(np.hanning(BLOCK), np.hanning(BLOCK)).astype(np.float32)


def probe(path):
    """Width, height and every frame's own time."""
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:frame=pts_time", "-of", "json", path],
        capture_output=True, check=True).stdout)
    stream = info["streams"][0]
    times = np.array([float(f["pts_time"]) for f in info["frames"] if "pts_time" in f])
    return stream["width"], stream["height"], times


def frames(path, width, height, size=WIDTH, colour=False, start=None, seconds=None):
    """Every frame as it is stored, none made up or dropped: grey at `size` wide, or
    the full picture in colour."""
    if colour:
        wide, tall, fmt, depth = width, height, "rgb24", 3
        scale = []
    else:
        wide, tall, fmt, depth = size, int(round(height * size / width / 2)) * 2, "gray", 1
        scale = ["-vf", f"scale={wide}:{tall}:flags=area"]
    reader = subprocess.Popen(
        ["ffmpeg", "-v", "error", *(["-ss", f"{start}"] if start is not None else []), "-i", path,
         *(["-t", f"{seconds}"] if seconds is not None else []),
         "-fps_mode", "passthrough", "-enc_time_base", "demux", *scale,
         "-f", "rawvideo", "-pix_fmt", fmt, "-"],
        stdout=subprocess.PIPE)
    shape = (tall, wide, depth) if depth > 1 else (tall, wide)
    size_bytes = wide * tall * depth
    try:
        while True:
            raw = reader.stdout.read(size_bytes)
            if len(raw) < size_bytes:
                break
            frame = np.frombuffer(raw, np.uint8).reshape(shape)
            yield frame if colour else frame.astype(np.float32)
    finally:
        reader.kill()
        reader.wait()


def spread(path, width, height, **cut):
    """How much each analysis pixel varies over the video."""
    total = squares = None
    count = 0
    for frame in frames(path, width, height, **cut):
        total = frame.copy() if total is None else total + frame
        squares = frame * frame if squares is None else squares + frame * frame
        count += 1
    return np.sqrt(np.maximum(squares / count - (total / count) ** 2, 0))


def moving_blocks(spread):
    """The corners of the blocks that change over the video, half overlapping."""
    moving = spread > CHANGING
    half = BLOCK // 2
    return [(y, x) for y in range(0, moving.shape[0] - BLOCK + 1, half)
            for x in range(0, moving.shape[1] - BLOCK + 1, half)
            if moving[y:y + BLOCK, x:x + BLOCK].mean() > 0.9]


def spectra(frame, corners):
    stack = np.stack([frame[y:y + BLOCK, x:x + BLOCK] for y, x in corners])
    stack = stack - stack.mean(axis=(1, 2), keepdims=True)
    return np.fft.rfft2(stack * _WINDOW)


def vectors(a, b):
    """How far each block of b moved from a's (dx, dy, in analysis pixels), and how
    sure: the correlation peak's height."""
    cross = np.conj(a) * b
    cross /= np.abs(cross) + 1e-6
    surface = np.fft.irfft2(cross, s=(BLOCK, BLOCK))
    flat = surface.reshape(len(surface), -1).argmax(axis=1)
    y, x = np.unravel_index(flat, (BLOCK, BLOCK))
    rows = np.arange(len(surface))
    here = surface[rows, y, x]

    def vertex(minus, plus):
        bend = minus - 2 * here + plus
        return np.where(bend < 0, 0.5 * (minus - plus) / np.where(bend < 0, bend, -1), 0.0)

    dy = y + vertex(surface[rows, y - 1, x], surface[rows, (y + 1) % BLOCK, x])
    dx = x + vertex(surface[rows, y, x - 1], surface[rows, y, (x + 1) % BLOCK])
    dy = np.where(dy > BLOCK / 2, dy - BLOCK, dy)
    dx = np.where(dx > BLOCK / 2, dx - BLOCK, dx)
    return dx, dy, here


def step(a, b):
    """How far the moving picture went from a to b, and whether it is the same
    picture at all (False across a cut)."""
    dx, dy, peak = vectors(a, b)
    return float(np.median(np.hypot(dx, dy))), bool(np.median(peak) >= PEAK)


def affine(a, b, corners):
    """The motion from a to b as one affine map, fitted to the blocks that agree:
    (6,) coefficients of dx = c0 + c1 x + c2 y, dy = c3 + c4 x + c5 y, in analysis
    pixels. Blocks over something held still (a plane the camera follows) disagree
    and are left out."""
    dx, dy, _ = vectors(a, b)
    centres = np.array(corners, np.float64) + BLOCK / 2
    design = np.column_stack([np.ones(len(centres)), centres[:, 1], centres[:, 0]])
    keep = np.ones(len(centres), bool)
    for _ in range(3):
        cx = np.linalg.lstsq(design[keep], dx[keep], rcond=None)[0]
        cy = np.linalg.lstsq(design[keep], dy[keep], rcond=None)[0]
        miss = np.hypot(design @ cx - dx, design @ cy - dy)
        limit = max(3 * np.median(miss[keep]), 0.1)
        if (miss <= limit).sum() < 3:
            break
        keep = miss <= limit
    return np.concatenate([cx, cy])
