import argparse
import csv
import io
import re
import os
import opentimelineio as otio

def timestamp_from_samples(samples, rate, fps):
    return otio.opentime.to_timecode(otio.opentime.from_seconds(seconds_from_samples(samples, rate)), fps)

def seconds_from_samples(samples, rate):
    return samples/rate

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

def extract_sample_rate(infile):
    with open(infile, 'r') as file:
        for line in file:
            if "Sample Rate:" in line:
                return int(line.split(':', 1)[1].strip())
    raise ValueError(f"Sample rate not found in EDL {infile}")

def clean_name(name):
    return name.split('_', 1)[-1] if '_' in name else name

def convert_samplitude_to_csv(infile, outfile, track_number, fps):
    title = extract_title(infile)
    sample_rate = extract_sample_rate(infile)
    
    with open(outfile, 'w', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow([
            "Source",
            "Source In (Seconds)",
            "Source In (TC)",
            "Source Out (Seconds)",
            "Source Out (TC)",
            "Destination In (Seconds)",
            "Destination In (TC)",
            "Destination Out (Seconds)",
            "Destination Out (TC)",
        ])
        
        process_lines = False
        with open(infile, 'r') as in_file:
            for line in in_file:
                if line.startswith(f"Track {track_number}:"):
                    process_lines = True
                    continue
                if process_lines and not line.startswith('#') and line.strip():
                    parsed_line = parse_edl_line(line)
                    if parsed_line and len(parsed_line) >= 16:
                        _, _, play_in, play_out, record_in, record_out, *_ = parsed_line[:6]
                        name = clean_name(parsed_line[15].rsplit('.', 1)[0])
                        
                        play_in = int(play_in)
                        play_out = int(play_out)
                        record_in = int(record_in)
                        record_out = int(record_out)
                        
                        csv_writer.writerow([
                            name,
                            seconds_from_samples(record_in, sample_rate),
                            timestamp_from_samples(record_in, sample_rate, fps),
                            seconds_from_samples(record_out, sample_rate),
                            timestamp_from_samples(record_out, sample_rate, fps),
                            seconds_from_samples(play_in, sample_rate),
                            timestamp_from_samples(play_in, sample_rate, fps),
                            seconds_from_samples(play_out, sample_rate),
                            timestamp_from_samples(play_out, sample_rate, fps),
                        ])

def main():
    parser = argparse.ArgumentParser(description="Convert Samplitude EDL to CSV format with video timestamps.")
    parser.add_argument("--infile", type=str, required=True, help="Input EDL file path")
    parser.add_argument("--track", type=int, default="1", help="Track number to process")
    parser.add_argument("--fps", type=float, required=True, help="Frame rate (no default value)")
    
    args = parser.parse_args()
    
    infile_dir = os.path.dirname(args.infile)
    infile_basename = os.path.basename(args.infile)
    outfile = os.path.join(infile_dir, os.path.splitext(infile_basename)[0] + ".csv")
    
    print(f"Writing CSV to {outfile}")
    convert_samplitude_to_csv(args.infile, outfile, args.track, args.fps)

if __name__ == "__main__":
    main()
