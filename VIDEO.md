# Video

Notes for working on picture, as MIXING.md is for sound.

## Resolve's API

- `TimelineItem.GetLeftOffset()` returns **timeline frames, not clip frames**.
  A clip with an FPS override — 50 fps S&Q footage in a 25 fps timeline —
  reports half the number its own rate would give, so dividing by the clip's
  FPS reads every source in-point at half its real value.
