pip install -r requirements.txt

Convert Samplitude EDL to OpenTimelineIO:
```
python3.9 edl2otio.py --infile ~/Desktop/Erlebach.edl --track 1 --fps 29.97002997002997
```

Convert Samplitude EDL to human-readable CSV edit decision list:
```
python3.9 edl2csv.py --infile ~/Desktop/Erlebach.edl --track 1 --fps 25
```

Export Reaper region directly to OpenTimelineIO (bypassing EDL):
```
/Applications/REAPER.app/Contents/MacOS/REAPER "project.rpp" "region_to_otio.lua" -close:nosave:exit
```

Configuration options in `region_to_otio.lua`:
- `region_name`: Set to the region name to export (e.g., "E1")
- `render_audio`: Set to `true` to also render a 48kHz/24-bit WAV mix of the region to `../Mixes/` folder
