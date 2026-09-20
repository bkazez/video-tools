# Video

Notes for working on picture, as MIXING.md is for sound.

## Resolve's API

- `TimelineItem.GetLeftOffset()` returns **timeline frames, not clip frames**.
  A clip with an FPS override — 50 fps S&Q footage in a 25 fps timeline —
  reports half the number its own rate would give, so dividing by the clip's
  FPS reads every source in-point at half its real value.
- `AppendToTimeline` honours `startFrame` on video and **ignores it on audio**.
  A film that must open past the talking at the head of a take gets there by
  rendering the audio already trimmed, not by trimming it in the timeline.

## Stacking angles, one per track

This is what Resolve itself builds: opening a multicam clip in a timeline
"replaces the contents of the Timeline with a vertical stack of superimposed
angles, one per track, each of which is offset from the beginning of the
Timeline to align with one another"
([manual, Opening and Altering Multicam Clips](https://www.steakunderwater.com/VFXPedia/__man/Resolve18-6/DaVinciResolve18_Manual_files/part1039.htm)).
Build a multi-angle edit that way rather than as one row of cuts:

- **One angle per track, highest track wins.** A shot is revealed by blading or
  disabling the tracks above it, not by moving anything, so lengthening or
  deleting a shot cannot open a hole under it.
- **The angle whose sync is still in doubt is ONE clip spanning the whole film,
  on the lowest track.** One clip is nudged once — select it and use `,` and
  `.`, the same keys the manual gives for sliding an angle inside a multicam
  clip — where several cuts of it have to be dragged into agreement one at a
  time. On the bottom it doubles as the fallback: any second no other angle
  covers shows it instead of black.
- **Name the tracks.** In a multicam clip the track name *is* the angle name;
  in a stack it is the only label that says which camera a row is.
- Resolve's scripting API has no multicam-clip constructor (`README.txt` under
  `Developer/Scripting` lists none), so a built project gets the stack and not
  the multicam clip. Converting one afterwards is by hand in the Media Pool.
