#!/usr/bin/env python3

import argparse
import csv
import os

def convert_csv_to_cmx3600(infile, outfile, title="UNTITLED"):
    """Convert CSV (from edl2csv.py) to CMX 3600 EDL format for Premiere import."""
    
    with open(infile, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        
        with open(outfile, 'w') as f:
            # Write CMX 3600 header
            f.write(f"TITLE: {title}\n")
            f.write("FCM: NON-DROP FRAME\n\n")
            
            edit_number = 1
            
            for row in reader:
                source_name = row['Source']
                source_in_tc = row['Source In (TC)']
                source_out_tc = row['Source Out (TC)']
                record_in_tc = row['Destination In (TC)']
                record_out_tc = row['Destination Out (TC)']
                
                # Write CMX 3600 edit entry
                # Format: EDIT_NUM  CLIP_NAME  TRACK  TRANSITION  SOURCE_IN  SOURCE_OUT  RECORD_IN  RECORD_OUT
                f.write(f"{edit_number:03d}  {source_name:<32} V     C        {source_in_tc} {source_out_tc} {record_in_tc} {record_out_tc}\n")
                
                edit_number += 1
    
    print(f"Successfully converted {infile} to CMX 3600 EDL: {outfile}")

def main():
    parser = argparse.ArgumentParser(description="Convert CSV (from edl2csv.py) to CMX 3600 EDL format for Premiere import.")
    parser.add_argument("--infile", type=str, required=True, help="Input CSV file path")
    parser.add_argument("--outfile", type=str, help="Output EDL file path (optional, defaults to input filename with .edl extension)")
    parser.add_argument("--title", type=str, help="Project title (optional, defaults to input filename)")
    
    args = parser.parse_args()
    
    # Generate output filename if not provided
    if not args.outfile:
        infile_dir = os.path.dirname(args.infile)
        infile_basename = os.path.basename(args.infile)
        outfile = os.path.join(infile_dir, os.path.splitext(infile_basename)[0] + ".edl")
    else:
        outfile = args.outfile
    
    # Generate title if not provided
    if not args.title:
        title = os.path.splitext(os.path.basename(args.infile))[0].upper()
    else:
        title = args.title.upper()
    
    convert_csv_to_cmx3600(args.infile, outfile, title)

if __name__ == "__main__":
    main()