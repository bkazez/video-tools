#!/usr/bin/env python3

import argparse
import os

import opentimelineio as otio

DEFAULT_SAMPLE_RATE = 48000
DEFAULT_FADE_CURVE = '"*default"'


def find_track(timeline, track_name):
    """Find a track by name. Returns the first match or raises an error."""
    available = []
    for track in timeline.tracks:
        available.append(track.name)
        if track.name == track_name:
            return track
    raise ValueError(
        f"Track {track_name!r} not found. Available tracks: {available}"
    )


def rational_time_to_samples(rt, sample_rate):
    """Convert a RationalTime to an integer sample position."""
    return round(rt.to_seconds() * sample_rate)


def build_source_table(track):
    """Build a mapping of unique source file paths to 1-based source indices."""
    source_paths = {}
    index = 1
    for child in track:
        if child.schema_name() != "Clip":
            continue
        path = source_url_from_clip(child)
        if path and path not in source_paths:
            source_paths[path] = index
            index += 1
    return source_paths


def source_url_from_clip(clip):
    """Extract the source file URL/path from a clip's media reference, if available."""
    mr = clip.media_reference
    if hasattr(mr, "target_url"):
        return mr.target_url
    return None


def media_start_offset_sec(clip):
    """Return the media file's available_range start time in seconds.

    OTIO source_range times are absolute (session timeline positions).
    The media's available_range.start_time tells us where the file begins
    in that timeline. Subtracting it gives the offset from byte 0 of the file.
    """
    mr = clip.media_reference
    if mr and mr.available_range:
        return mr.available_range.start_time.to_seconds()
    return 0.0


def format_edit_line(source_idx, track_num, play_in, play_out, record_in, record_out,
                     fade_in, fade_out, name):
    """Format a single Samplitude EDL edit line (16 fields)."""
    vol_db = 0.0
    mute = 0
    lock = 0
    fade_pct = 0
    return (
        f"{source_idx:>6d} {track_num:>5d} {play_in:>12d} {play_out:>12d}"
        f" {record_in:>12d} {record_out:>12d}"
        f" {vol_db:>8.1f} {mute:>2d} {lock:>2d}"
        f" {fade_in:>12d} {fade_pct:>5d} {DEFAULT_FADE_CURVE:>34s}"
        f" {fade_out:>12d} {fade_pct:>5d} {DEFAULT_FADE_CURVE:>34s}"
        f' "{name}"'
    )


def convert_otio_to_samplitude_edl(timeline, track, sample_rate, title):
    """Convert a single OTIO track to a Samplitude EDL string."""
    source_table = build_source_table(track)

    lines = []
    lines.append("Samplitude EDL File Format Version 1.5")
    lines.append(f'Title: "{title}"')
    lines.append(f"Sample Rate: {sample_rate}")
    lines.append("Output Channels: 2")
    lines.append("")

    # Source table
    lines.append(f"Source Table Entries: {len(source_table)}")
    for path, idx in source_table.items():
        lines.append(f'   {idx} "{path}"')
    lines.append("")

    # Collect clips with their timeline positions and fade info
    clips_data = []
    timeline_cursor_sec = 0.0

    children = list(track)
    i = 0
    while i < len(children):
        child = children[i]

        if child.schema_name() == "Transition":
            transition = child
            in_offset_sec = transition.in_offset.to_seconds()
            out_offset_sec = transition.out_offset.to_seconds()

            # Transition overlaps: back up by in_offset
            timeline_cursor_sec -= in_offset_sec

            # Apply fade_out to previous clip
            if clips_data and in_offset_sec > 0:
                clips_data[-1]["fade_out"] = round(in_offset_sec * sample_rate)

            # The next child should be a clip
            if i + 1 < len(children) and children[i + 1].schema_name() == "Clip":
                i += 1
                clip = children[i]
                dur_sec = clip.source_range.duration.to_seconds()
                src_offset_sec = clip.source_range.start_time.to_seconds() - media_start_offset_sec(clip)

                fade_in_samples = round(out_offset_sec * sample_rate)

                clips_data.append({
                    "clip": clip,
                    "play_in_sec": timeline_cursor_sec,
                    "play_out_sec": timeline_cursor_sec + dur_sec,
                    "record_in_sec": src_offset_sec,
                    "record_out_sec": src_offset_sec + dur_sec,
                    "fade_in": fade_in_samples,
                    "fade_out": 0,
                })
                timeline_cursor_sec += dur_sec

        elif child.schema_name() == "Clip":
            clip = child
            dur_sec = clip.source_range.duration.to_seconds()
            src_offset_sec = clip.source_range.start_time.to_seconds() - media_start_offset_sec(clip)

            clips_data.append({
                "clip": clip,
                "play_in_sec": timeline_cursor_sec,
                "play_out_sec": timeline_cursor_sec + dur_sec,
                "record_in_sec": src_offset_sec,
                "record_out_sec": src_offset_sec + dur_sec,
                "fade_in": 0,
                "fade_out": 0,
            })
            timeline_cursor_sec += dur_sec

        elif child.schema_name() == "Gap":
            timeline_cursor_sec += child.source_range.duration.to_seconds()

        i += 1

    # Write track section
    track_num = 1
    lines.append(f'Track {track_num}: "{track.name}" Solo: 0 Mute: 0')
    for cd in clips_data:
        source_path = source_url_from_clip(cd["clip"]) or ""
        source_idx = source_table.get(source_path, 1)

        play_in = round(cd["play_in_sec"] * sample_rate)
        play_out = round(cd["play_out_sec"] * sample_rate)
        record_in = round(cd["record_in_sec"] * sample_rate)
        record_out = round(cd["record_out_sec"] * sample_rate)

        lines.append(format_edit_line(
            source_idx, track_num, play_in, play_out,
            record_in, record_out,
            cd["fade_in"], cd["fade_out"],
            cd["clip"].name,
        ))
    lines.append("")

    # Volume and pan envelopes
    lines.append(f"Volume for Track {track_num}:")
    lines.append(" 0 0.000")
    lines.append("")
    lines.append(f"Pan for Track {track_num}:")
    lines.append(" 0 0.00000")
    lines.append("")

    return "\n".join(lines) + "\n"


def list_tracks(timeline):
    """Print available tracks and their clip counts."""
    for i, track in enumerate(timeline.tracks):
        kind = "Audio" if track.kind == otio.schema.TrackKind.Audio else "Video"
        clips = sum(1 for c in track if c.schema_name() == "Clip")
        print(f"  [{i}] {track.name!r} ({kind}, {clips} clips)")


def main():
    parser = argparse.ArgumentParser(
        description="Convert an OTIO track to Samplitude EDL format (for Reaper import)."
    )
    parser.add_argument(
        "--infile", type=str, required=True, help="Input OTIO file path"
    )
    parser.add_argument(
        "--outfile", type=str, default=None,
        help="Output EDL file path (defaults to input with .edl extension)",
    )
    parser.add_argument(
        "--track", type=str, default=None,
        help="Track name to export (e.g. 'Audio 4')",
    )
    parser.add_argument(
        "--sample-rate", type=int, default=DEFAULT_SAMPLE_RATE,
        help=f"Output sample rate (default: {DEFAULT_SAMPLE_RATE})",
    )
    parser.add_argument(
        "--title", type=str, default=None,
        help="EDL title (default: derived from input filename)",
    )
    parser.add_argument(
        "--list-tracks", action="store_true",
        help="List available tracks and exit",
    )

    args = parser.parse_args()

    timeline = otio.adapters.read_from_file(args.infile)

    if args.list_tracks:
        list_tracks(timeline)
        return

    if not args.track:
        parser.error("--track is required (use --list-tracks to see available tracks)")

    track = find_track(timeline, args.track)
    title = args.title or os.path.splitext(os.path.basename(args.infile))[0]

    edl_string = convert_otio_to_samplitude_edl(
        timeline, track, args.sample_rate, title
    )

    outfile = args.outfile
    if outfile is None:
        outfile = os.path.splitext(args.infile)[0] + ".edl"

    with open(outfile, "w") as f:
        f.write(edl_string)

    print(f"Wrote {outfile}")


if __name__ == "__main__":
    main()
