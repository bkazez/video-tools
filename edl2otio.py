import argparse
import csv
import io
import re
import opentimelineio as otio
import os

def opentime_from_samples(samples, rate):
    return otio.opentime.from_seconds(samples/rate)

def parse_edl_line(line):
    reader = csv.reader(io.StringIO(line), delimiter=' ', skipinitialspace=True, quotechar='"')
    for row in reader:
        return row

def extract_title(infile):
    with open(infile, 'r') as file:
        for line in file:
            if "Title:" in line:
                return line.split(':', 1)[1].strip()
    return "Unknown Project"

def extract_track_name(line):
    match = re.search(r'Track \d+: "(.*?)"', line)
    if match:
        return match.group(1)
    return None

def extract_sample_rate(infile):
    with open(infile, 'r') as file:
        for line in file:
            if "Sample Rate:" in line:
                return int(line.split(':', 1)[1].strip())
    raise ValueError(f"Sample rate not found in EDL {infile}")

def clean_name(name):
    cleaned_name = name.split('_', 1)[-1] if '_' in name else name
    return cleaned_name

def read_take_definition_edl(take_def_edl, expected_sample_rate, fps):
    sample_rate = extract_sample_rate(take_def_edl)
    if sample_rate != expected_sample_rate:
        # We could store everything as floating-point seconds but that seems risky for floating point errors.
        raise ValueError(f"Error: Expected take definition EDL sample rate ({sample_rate}) to match sample rate of input EDL ({expected_sample_rate})' - change #{take_def_edl}'s sample rate in Reaper.")

    take_def = {}
    with open(take_def_edl, 'r') as in_file:
        process_lines = False
        for line in in_file:
            if line.startswith("Track ") and process_lines:
                break
            if line.startswith("Track 1:"):
                process_lines = True
                continue
            if process_lines and not line.startswith('#') and line.strip():
                parsed_line = parse_edl_line(line)
                if parsed_line and len(parsed_line) >= 16:
                    _, _, play_in, _, record_in, *_ = parsed_line[:5]
                    play_in = int(play_in)
                    name = clean_name(parsed_line[15])
                    if name in take_def:
                        play_in = opentime_from_samples(play_in, sample_rate)
                        raise ValueError(f"Error: Duplicate '{name}' - see #{take_def_edl}, {otio.opentime.to_time_string(play_in)}")
                    take_def[name] = int(record_in)
    return take_def

def convert_samplitude_to_otio(infile, take_def_edl, outfile, track_number, fps, soundtrack, from_play_in, to_play_out):
    title = extract_title(infile)
    sample_rate = extract_sample_rate(infile)

    if from_play_in is not None and to_play_out is not None:
        print(f"Only extracting from {from_play_in} to {to_play_out}")

    # Read take definition EDL to create a map of media item play-in times
    take_def = None
    if take_def_edl is not None:
        take_def = read_take_definition_edl(take_def_edl, sample_rate, fps)

    timeline = otio.schema.Timeline(name=title)
    timeline.global_start_time = otio.opentime.RationalTime(0, sample_rate)
    video_track = otio.schema.Track(name=f"Track {track_number}")

    process_lines = False
    audio_duration = 0
    audio_track_name = None

    with open(infile, 'r') as in_file:
        for line in in_file:
            if line.startswith("Track ") and process_lines:
                break

            if line.startswith(f"Track {track_number}:"):
                audio_track_name = extract_track_name(line)
                if audio_track_name:
                    print(f"Track Name: {audio_track_name}")  # Print or store the track name as needed
                process_lines = True
                continue

            if process_lines and not line.startswith('#') and line.strip():
                parsed_line = parse_edl_line(line)
                if parsed_line and len(parsed_line) >= 16:
                    _, _, play_in, play_out, record_in, record_out, _, _, _, fade_in, _, _, fade_out, *_ = parsed_line[:13]

                    name = clean_name(parsed_line[15].rsplit('.', 1)[0])

                    play_in = int(play_in)
                    play_out = int(play_out)
                    record_in = int(record_in)
                    record_out = int(record_out)
                    fade_in = int(fade_in)
                    fade_out = int(fade_out)
                    audio_duration = play_out # this way, the last one will be the final Play-Out

                    # Exclude clips that start before from_play_in, or start after to_play_out.
                    # This means that we will never truncate an edit.
                    if (from_play_in and play_in < from_play_in) or (to_play_out and play_in > to_play_out):
                        continue

                    # We should only ever have crossfades, so previous's fade_out = current's fade_in
                    # We don't want overlapping clips in video, so we remove the fade outs.
                    # This will be wrong for the last track, but that's easy to fix in practice.
                    if fade_out > 0:
                        play_out -= fade_out
                        record_out -= fade_out

                    # Get the play-in time from the take definition EDL or default to zero
                    take_start_point_in_source = take_def.get(name, 0) if take_def else 0
                    source_in = record_in - take_start_point_in_source
                    source_out = record_out - take_start_point_in_source
                    print(f"{name}: adjusting [{record_in/sample_rate}, {record_out/sample_rate}] by {take_start_point_in_source/sample_rate}\t[{source_in/sample_rate}, {source_out/sample_rate}]")

                    media_reference = otio.core.MediaReference(
                        name=name,
                        available_range=otio.opentime.range_from_start_end_time(
                            opentime_from_samples(source_in, sample_rate),
                            opentime_from_samples(source_out, sample_rate)
                        )
                    )
                    video_clip = otio.schema.Clip(
                        name=name,
                        media_reference=media_reference
                    )
                    video_track.append(video_clip)

    timeline.tracks.append(video_track)

    # Create an audio track
    if soundtrack:
        audio_track = otio.schema.Track(name="Audio 1", kind=otio.schema.TrackKind.Audio)
        media_reference = otio.core.MediaReference(
            name=soundtrack,
            available_range=otio.opentime.range_from_start_end_time(
                opentime_from_samples(0, sample_rate),
                opentime_from_samples(audio_duration, sample_rate)
            )
        )
        audio_clip = otio.schema.Clip(
            name=soundtrack,
            media_reference=media_reference
        )
        audio_track.append(audio_clip)
        timeline.tracks.append(audio_track)

    # Write to file
    otio.adapters.write_to_file(timeline, outfile)

def main():
    parser = argparse.ArgumentParser(description="Convert Samplitude EDL to OpenTimelineIO format.")
    parser.add_argument("--infile", type=str, required=True, help="Input EDL file path")
    parser.add_argument("--take_def_edl", type=str, default=None, help="Take definition EDL file path")
    parser.add_argument("--track", type=int, default="1", help="Track number to process")
    parser.add_argument("--fps", type=float, required=True, help="Frame rate (no default value)")
    parser.add_argument("--soundtrack", type=str, default=None, help="Name of corresponding edited audio")
    parser.add_argument("--from_play_in", type=int, default=None, help="Optionally, start at this sample")
    parser.add_argument("--to_play_out", type=int, default=None, help="Optionally, end at this sample")

    args = parser.parse_args()

    # Derive the output filename from the input filename and ensure it's in the same directory
    infile_dir = os.path.dirname(args.infile)
    infile_basename = os.path.basename(args.infile)
    outfile = os.path.join(infile_dir, os.path.splitext(infile_basename)[0] + ".otio")

    print(f"Writing to {outfile}")

    convert_samplitude_to_otio(args.infile, args.take_def_edl, outfile, args.track, args.fps, args.soundtrack, args.from_play_in, args.to_play_out)

if __name__ == "__main__":
    main()
