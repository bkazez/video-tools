pip install -r requirements.txt

Convert Samplitude EDL to OpenTimelineIO:
```
python3.9 edl2otio.py --infile ~/Desktop/Erlebach.edl --track 1 --fps 29.97002997002997
```

Convert Samplitude EDL to human-readable CSV edit decision list:
```
python3.9 edl2csv.py --infile ~/Desktop/Erlebach.edl --track 1 --fps 25
```
