#!/usr/bin/env python3
"""The shared compositor: what it puts on a product's frames, and what it refuses.

    python3 tests/test_product_video.py

It is given ten grey frames standing in for a product and a storyboard with a
card, a title, a keystroke and a camera move, and asked whether the film that
comes out has the window, the words and the moves in it. Grey rather than
anything meaningful because none of this knows what a product is -- that is the
whole point of the split, and a test that needed a real app to check a title
would have missed it.

macOS only: the compositor is AppKit, because the look is that text rendering.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TOOL = HERE / "bin" / "product-video"
WIDTH, HEIGHT, FPS, FRAMES = 480, 270, 10, 20

failures = []


def check(label, ok, detail=""):
    print(f"  {'ok  ' if ok else 'FAIL'} {label}{'' if ok else '  -- ' + detail}")
    if not ok:
        failures.append(f"{label}: {detail}")


def product(tmp):
    """Ten frames of a product that does not exist, plus the timeline a frame
    source owes the compositor."""
    from PIL import Image
    frames = tmp / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    for index in range(FRAMES):
        Image.new("RGB", (WIDTH, HEIGHT), (40, 44, 52)).save(frames / f"{index:05d}.png")
    (frames / "timeline.json").write_text(json.dumps({
        "fps": FPS, "frames": FRAMES, "seconds": FRAMES / FPS,
        "width": WIDTH, "height": HEIGHT, "scale": 1,
        "title": "Something - 3 things",
        "camera": [{"at": 1.0, "to": 2.0, "seconds": 0.5, "x": 120, "y": 80}],
    }))
    return frames


def storyboard(tmp, **changes):
    board = {
        "seconds": FRAMES / FPS, "fps": FPS, "beat": 1.0,
        "events": [
            {"at": 0.0, "card": "One line.", "seconds": 0.6,
             "then": {"text": "And another.", "at": 0.3}},
            {"at": 1.0, "step": "1. A step", "seconds": 0.6},
            {"at": 1.0, "do": "key:up"},
        ],
    }
    board.update(changes)
    path = tmp / "board.json"
    path.write_text(json.dumps(board))
    return path


def run(argv):
    return subprocess.run([str(TOOL)] + argv, capture_output=True, text=True, timeout=300)


def dressing(tmp):
    """The window, the words and the camera, on frames that had none of them."""
    frames = product(tmp)
    board = storyboard(tmp)
    out = tmp / "film.mp4"
    done = run([str(board), "--frames", str(frames), "--out", str(out), "--width", "480"])
    check("a film comes out", done.returncode == 0 and out.exists(),
          done.stderr.strip() or "no file")
    if not out.exists():
        return

    from PIL import Image
    dressed = sorted((frames / "dressed").glob("*.png"))
    check("every frame was dressed", len(dressed) == FRAMES, str(len(dressed)))

    bar = Image.open(dressed[0]).convert("RGB")
    check("the window bar is above the product",
          bar.size == (WIDTH, HEIGHT + 30), str(bar.size))
    # The close button, 14 points in and 15 down from the top of a 30 point bar.
    red = bar.getpixel((20, 15))
    check("and it carries the three lights", red[0] > 180 and red[1] < 120, str(red))

    # A card dims the whole frame; a bare product frame is the grey it was made.
    card = Image.open(dressed[3]).convert("RGB").getpixel((40, 200))
    plain = Image.open(dressed[19]).convert("RGB").getpixel((40, 200))
    check("a card darkens the picture under it",
          sum(card) < sum(plain) - 30, f"{card} against {plain}")

    # Halfway through the camera move the picture is magnified, so the product's
    # own grey has been pushed off at least one edge of the frame.
    corner = Image.open(dressed[14]).convert("RGB").getpixel((WIDTH - 4, HEIGHT))
    check("the camera magnifies the picture", corner != (40, 44, 52), str(corner))


def standing_in_a_room(tmp):
    """A product too small to fill the picture: a bezel around it, footage behind
    it, and the two agreeing about where the glass is."""
    from PIL import Image
    room = tmp / "room"
    canvas, scale = (480, 270), 2
    wide, tall = canvas[0] * scale, canvas[1] * scale

    # The product is a flat green, the room a flat magenta. Nothing about either
    # matters except that no pixel of one can be mistaken for the other.
    frames = room / "frames"
    backdrop = room / "backdrop"
    frames.mkdir(parents=True, exist_ok=True)
    backdrop.mkdir(parents=True, exist_ok=True)
    for index in range(FRAMES):
        Image.new("RGB", (220, 478), (0, 200, 0)).save(frames / f"{index:05d}.png")
        Image.new("RGB", (wide, tall), (200, 0, 200)).save(backdrop / f"{index:05d}.png")
    (frames / "timeline.json").write_text(json.dumps({
        "fps": FPS, "frames": FRAMES, "width": 110, "height": 239, "scale": scale,
        "canvas": {"width": canvas[0], "height": canvas[1]},
        "chrome": "iphone-16-pro-max", "camera": [],
    }))

    board = storyboard(tmp, width=110, height=239, scale=scale,
                       chrome="iphone-16-pro-max",
                       canvas={"width": canvas[0], "height": canvas[1]})
    out = room / "film.mp4"
    done = run([str(board), "--frames", str(frames), "--backdrop", str(backdrop),
                "--out", str(out), "--width", str(wide)])
    check("a product in a room becomes a film", done.returncode == 0 and out.exists(),
          done.stderr.strip() or "no file")
    if not out.exists():
        return

    # The compositor is the only thing that decides where the phone stands, and
    # it says so, so the test can look exactly there rather than hunting.
    said = run([str(board), "--layout"])
    places = json.loads(said.stdout)
    glass = places["screen"]
    check("and it says where the glass is",
          places["canvas"] == {"width": wide, "height": tall}
          and 0 < glass["width"] < wide and 0 < glass["height"] < tall,
          said.stdout.strip())

    picture = Image.open(sorted((frames / "dressed").glob("*.png"))[0]).convert("RGB")
    check("the finished frame is the canvas, not the product",
          picture.size == (wide, tall), str(picture.size))

    middle = picture.getpixel((glass["x"] + glass["width"] // 2,
                               glass["y"] + glass["height"] // 2))
    check("the product lands inside the screen hole", middle[1] > 150 and middle[0] < 80,
          str(middle))

    # Beside the phone, at the same height: the room, dimmed but plainly itself.
    outside = picture.getpixel((glass["x"] // 2, tall // 2))
    check("and the room shows outside the bezel",
          outside[0] > 80 and outside[2] > 80 and outside[1] < 80, str(outside))

    # A bezel between the two: titanium is near-neutral, where the product is
    # flat green and the room flat magenta, so a grey pixel can only be the metal.
    edge = picture.getpixel((glass["x"] - 5, glass["y"] + glass["height"] // 2))
    check("with a bezel between them",
          max(edge) - min(edge) < 40 and max(edge) > 100, str(edge))

    # Footage that is not the canvas's own pixels cannot be what the product was
    # looking at, so it is refused rather than stretched.
    Image.new("RGB", (wide // 2, tall // 2), (200, 0, 200)).save(backdrop / "00000.png")
    done = run([str(board), "--frames", str(frames), "--backdrop", str(backdrop),
                "--out", str(out), "--width", str(wide)])
    check("a backdrop that is not the canvas's size fails the build",
          done.returncode != 0 and "backdrop" in done.stderr,
          done.stderr.strip() or "it was accepted")


def refusing(tmp):
    """The film's own rule: what a viewer reads lands on the beat."""
    board = storyboard(tmp, events=[{"at": 0.0, "card": "on", "seconds": 0.4},
                                    {"at": 0.35, "step": "off", "seconds": 0.4}])
    done = run([str(board), "--check"])
    check("a title off the beat fails the build",
          done.returncode != 0 and "grid" in done.stderr,
          done.stderr.strip() or "it was accepted")

    done = run([str(storyboard(tmp)), "--check"])
    check("and a storyboard on the beat passes", done.returncode == 0, done.stderr.strip())


def main():
    if sys.platform != "darwin":
        print("SKIP (the compositor is AppKit, so macOS only)")
        return
    try:
        import PIL  # noqa: F401
    except ImportError:
        print("SKIP (no Pillow, so the frames cannot be made or read back)")
        return

    tmp = Path(tempfile.mkdtemp(prefix="product-video-"))
    print(f"the compositor, over {FRAMES} frames of nothing in particular\n")
    dressing(tmp)
    standing_in_a_room(tmp)
    refusing(tmp)

    if failures:
        print("\n" + "\n".join(f"  - {f}" for f in failures))
        sys.exit(1)
    print("\nthe film's half is the film's, whatever the product was")


if __name__ == "__main__":
    main()
