#!/usr/bin/env python3
"""The lens-unit metadata parse, against synthesised KLV and against real clips.

    python3 tests/test_lens_metadata.py

Two halves, because neither one is enough on its own:

  * **Synthesised.** A KLV buffer built by hand proves the walk still finds the
    lens set and reads the local tags. It needs no media, so it runs anywhere.

  * **Real.** The 2026-04-07 session is the only material where it is known which
    clips held focus and which did not, and those verdicts are what the docs and
    both cinematic profiles are written against. Skipped when that folder is not
    on the machine, so this is a check rather than a dependency.

The numbers here are the ones quoted in docs/sony-zv-e10ii-presets.md.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import sonyrtmd as S

SESSION = os.path.expanduser(
    "~/Documents/Music/Recordings/2026-04-07 Brahms Faure/Video")

# Which clips of that session held focus, read off eight samples each. C0495 is
# the one that decides LENS_MOVE_FLOOR: its focus ring twitched 12 units of 65536
# while the zoom ring sat against its stop, which is quantisation, not a rack.
FOCUS_MOVED = {"C0488", "C0491", "C0492", "C0496", "C0497", "C0498"}
FOCUS_HELD = {"C0484", "C0485", "C0486", "C0487", "C0489", "C0490",
              "C0493", "C0494", "C0495", "C0499"}

failures = []


def check(name, got, want):
    if got != want:
        failures.append(f"{name}: got {got!r}, want {want!r}")


def klv(key, tags):
    """One KLV set with a short-form BER length, as the camera writes it."""
    value = b"".join(t.to_bytes(2, "big") + len(v).to_bytes(2, "big") + v
                     for t, v in tags.items())
    return key + len(value).to_bytes(1, "big") + value


# --- synthesised ------------------------------------------------------------

raw = {0x8000: 46527, 0x8001: 54677, 0x8004: 49938,
       0x8005: 49592, 0x800a: 50423, 0x800b: 37160}
buf = klv(S.KEY_LENS_UNIT, {t: v.to_bytes(2, "big") for t, v in raw.items()})
parsed = S.parse_rtmd(buf)
for tag, name in S.LENS_TAGS.items():
    check(f"parse {name}", parsed.get(name), raw[tag])

# The aperture ladder. These three values are every aperture the 2026-04-07
# session used, and each one has to land on a stop a camera actually displays --
# a wrong formula does not do that three times running.
for value, want in ((46527, 3.2), (50687, 4.5), (53343, 5.6)):
    stop, fit = S.f_number(value)
    check(f"f_number({value})", stop, want)
    if fit > S.STOP_TOLERANCE:
        failures.append(f"f_number({value}): {fit:.1%} off the ladder")

# A twitch under the floor is not a move; one over it is.
held = [(0.0, {"focus_ring_raw": 54222}), (60.0, {"focus_ring_raw": 54234})]
moved = [(0.0, {"focus_ring_raw": 53088}), (60.0, {"focus_ring_raw": 54336})]
check("12 units is quantisation", S.lens_movement(held)["focus"]["moved"], False)
check("1248 units is a rack", S.lens_movement(moved)["focus"]["moved"], True)
check("moved reports when", S.lens_movement(moved)["focus"]["at"], 60.0)

# --- real -------------------------------------------------------------------

if os.path.isdir(SESSION):
    for stem in sorted(FOCUS_MOVED | FOCUS_HELD):
        # Eight samples, the spread the verdicts were established at, but without
        # describe()'s audio and picture passes -- those decode the whole clip and
        # have nothing to do with the lens.
        path = os.path.join(SESSION, f"{stem}.MP4")
        series = S.lens_series(path, S.probe(path)["duration"], 8)
        check(f"{stem} focus", S.lens_movement(series)["focus"]["moved"],
              stem in FOCUS_MOVED)
    # A body that writes no lens set must cost no seeks and claim nothing.
    dji = S.describe(os.path.join(SESSION, "DJI_0689.MP4"))
    check("DJI has no lens metadata", "lens" in dji, False)
    print(f"real material: {len(FOCUS_MOVED | FOCUS_HELD)} clips of 2026-04-07")
else:
    print(f"real material: SKIPPED, no {SESSION}")

if failures:
    print("\n".join("FAIL  " + f for f in failures))
    sys.exit(1)
print("lens metadata: ok")
