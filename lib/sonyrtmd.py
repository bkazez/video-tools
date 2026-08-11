"""Reading Sony XAVC real-time metadata (rtmd) out of a clip.

Sony cameras write a per-frame metadata track alongside the picture, holding the
camera model, the capture frame rate, exposure, white balance, the embedded
monitoring LUT and a wall clock. The CLIP/*.XML sidecars on the card carry the
same information, but those are left behind whenever clips are copied off as
bare .MP4 -- the rtmd travels inside the file, so it survives.

Shared by bin/sony-clip-info and bin/camera-session-sync.
"""
import datetime, glob, json, math, os, re, subprocess, sys

# The Camera Unit Metadata set (SMPTE RDD 18) and the Sony private set that
# carries the acquisition clock.
KEY_CAMERA_UNIT = bytes.fromhex("060e2b34025301010c02010102010000")
KEY_SONY_CLOCK  = bytes.fromhex("060e2b34025301010c0201017f010000")

# Local tags, established empirically against clips whose settings were known --
# published RDD 18 tag lists do not agree with what these bodies write, so every
# one of these is anchored to something checkable:
#   0x8104/0x8105  imager dimensions in um; the ratio must come out at exactly
#                  16:9 or 3:2, which is how you know the KLV walk has not drifted
#   0x8106         capture frame rate, verified against a clip proven 2x slow
#   0x8109         shutter, a rational near 1/(frame rate)
#   0x810a         master gain, SIGNED, in 1/100 dB -- reads near 65000 when negative
#   0x810b         ISO. 0x8115 carries the same value
#   0x810e         white balance in K
# Gain and ISO cross-check each other: ISO = 800 * 10^(dB/20) on these bodies,
# which held to within a rounding step on every clip tested across three shoots.
# 0x810a was briefly labelled ISO on the strength of one clip where it happened
# to read 1600; the next shoot read 64736, which is -800, which is -8 dB.
CAMERA_TAGS = {
    0x8104: "imager_width_um",
    0x8105: "imager_height_um",
    0x8106: "capture_fps",
    0x8109: "shutter_s",
    0x810a: "master_gain_centidb",
    0x810b: "iso",
    0x810e: "white_balance_k",
    0x8114: "model_serial",
}
TAG_CLOCK = 0xe304

# The Lens Unit set, the other half of the same RDD 18 family. It is what answers
# "did anything refocus during this take", which no other reading of the file can:
# a rack in the middle of a twenty-minute take looks like ordinary footage to
# ffprobe. Names follow telemetry-parser's src/sony/rtmd_tags.rs.
#
# Only the aperture is decoded, and it is anchored: F = 2^((v-32768)/8192) turns
# the three values the 2026-04-07 session used -- 46527, 50687, 53343 -- into
# f/3.2, f/4.5 and f/5.6, three standard third-stop marks, which a wrong formula
# does not land on three times running.
#
# The distance and focal-length encodings are deliberately NOT decoded. The same
# formula reads 4.2 on a clip whose zoom ring sits at its stop, which is neither
# end of any lens here, so nothing anchors them and a number would be a guess.
# Their raw values still say whether something moved, which is all the check needs.
KEY_LENS_UNIT = bytes.fromhex("060e2b34025301010c02010101010000")
LENS_TAGS = {
    0x8000: "iris_f_raw",
    0x8001: "focus_distance_raw",
    0x8004: "zoom_35mm_raw",
    0x8005: "focal_length_raw",
    0x800a: "focus_ring_raw",
    0x800b: "zoom_ring_raw",
}
LENS_GROUPS = {
    "focus": ("focus_distance_raw", "focus_ring_raw"),
    "zoom": ("zoom_35mm_raw", "focal_length_raw", "zoom_ring_raw"),
    "aperture": ("iris_f_raw",),
}

# A lens nobody touches reads bit-identical for a whole take: nine of the sixteen
# clips of 2026-04-07 did, over takes as long as 28 minutes. So the floor is not a
# tolerance for real movement but for quantisation -- C0495 twitched its focus ring
# by 12 units of 65536 while the zoom ring sat hard against its stop. 64 units is
# 0.1% of full scale, an order of magnitude below the smallest real move measured
# (445 units, C0492).
LENS_MOVE_FLOOR = 64


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, **kw)


def probe(path):
    """Container facts from ffprobe."""
    out = run(["ffprobe", "-v", "error", "-show_streams", "-show_format",
               "-of", "json", path], text=True).stdout
    d = json.loads(out)
    info = {"duration": float(d["format"].get("duration", 0)),
            "size": int(d["format"].get("size", 0)),
            "brand": d["format"].get("tags", {}).get("major_brand", ""),
            "created_tag": d["format"].get("tags", {}).get("creation_time", "")}
    for s in d["streams"]:
        t = s["codec_type"]
        if t == "video" and "width" not in info:
            num, den = (int(x) for x in s["r_frame_rate"].split("/"))
            info.update(width=s["width"], height=s["height"],
                        container_fps=num / den if den else 0,
                        codec=s.get("codec_name"), pix_fmt=s.get("pix_fmt"),
                        color_range=s.get("color_range", "unknown"),
                        color_transfer=s.get("color_transfer", "unknown"))
        elif t == "audio" and "audio_codec" not in info:
            info.update(audio_codec=s.get("codec_name"),
                        audio_channels=s.get("channels"))
        elif t == "data":
            info["data_stream"] = s["index"]
            info["timecode"] = s.get("tags", {}).get("timecode")
    return info


def read_rtmd(path, seconds=0.5, from_end=False, duration=None, at=None):
    """Raw bytes of the timed-metadata track, from the head, the tail or a point.

    Seeking is done on the input, so reading anywhere but the head costs a seek
    rather than a pass over the file -- which matters when a clip is ten gigabytes,
    and is what makes sampling a take at eight points affordable.
    """
    cmd = ["ffmpeg", "-v", "error"]
    if at is not None:
        cmd += ["-ss", str(max(0.0, at)), "-t", str(seconds)]
    elif from_end and duration:
        cmd += ["-ss", str(max(0, duration - 2)), "-t", "2"]
    else:
        cmd += ["-t", str(seconds)]
    cmd += ["-i", path, "-map", "0:d:0", "-c", "copy", "-f", "data", "-"]
    return run(cmd).stdout


def ber_length(buf, p):
    """SMPTE BER length: short form, or 0x8n followed by n length bytes."""
    b = buf[p]
    if b < 0x80:
        return b, p + 1
    n = b & 0x7f
    return int.from_bytes(buf[p + 1:p + 1 + n], "big"), p + 1 + n


def walk_klv(buf):
    """Yield (key, {local_tag: value_bytes}) for each KLV set in the buffer."""
    p = 0
    while p + 17 < len(buf):
        key = buf[p:p + 16]
        if not key.startswith(b"\x06\x0e\x2b\x34"):
            p += 1                       # padding between frames; resynchronise
            continue
        try:
            length, q = ber_length(buf, p + 16)
        except IndexError:
            return
        value = buf[q:q + length]
        tags, r = {}, 0
        while r + 4 <= len(value):
            tag = int.from_bytes(value[r:r + 2], "big")
            ln = int.from_bytes(value[r + 2:r + 4], "big")
            tags[tag] = value[r + 4:r + 4 + ln]
            r += 4 + ln
        yield key, tags
        p = q + length


def bcd(b):
    return (b >> 4) * 10 + (b & 0x0f)


def parse_clock(v):
    """Sony acquisition clock: flag byte, then BCD YYYY MM DD HH MM SS."""
    if len(v) < 8:
        return None
    return (f"{bcd(v[1]):02d}{bcd(v[2]):02d}-{bcd(v[3]):02d}-{bcd(v[4]):02d} "
            f"{bcd(v[5]):02d}:{bcd(v[6]):02d}:{bcd(v[7]):02d}")


def rational(v):
    if len(v) != 8:
        return None
    a = int.from_bytes(v[:4], "big")
    b = int.from_bytes(v[4:], "big")
    return (a, b)


def parse_rtmd(buf):
    """Everything we understand from one buffer of rtmd."""
    out, luts = {}, []
    for key, tags in walk_klv(buf):
        if key == KEY_CAMERA_UNIT:
            for tag, v in tags.items():
                name = CAMERA_TAGS.get(tag)
                if name == "model_serial":
                    out[name] = v.split(b"\x00")[0].decode("ascii", "replace").strip()
                elif name in ("capture_fps", "shutter_s"):
                    out[name] = rational(v)
                elif name:
                    out[name] = int.from_bytes(v, "big")
        elif key == KEY_LENS_UNIT:
            for tag, v in tags.items():
                name = LENS_TAGS.get(tag)
                if name:
                    out[name] = int.from_bytes(v, "big")
        elif key == KEY_SONY_CLOCK:
            if TAG_CLOCK in tags:
                out.setdefault("clock", parse_clock(tags[TAG_CLOCK]))
        for v in tags.values():
            if b".cube" in v:
                name = v.split(b"\x00")[0].decode("ascii", "replace")
                if name not in luts:
                    luts.append(name)
    if luts:
        out["embedded_lut"] = luts
    return out


# The third-stop ladder a camera displays. Snapping to it is not cosmetic: a lens
# is set on one of these rungs, so a decoded value that lands between two of them
# says the formula is wrong, the same way the imager aspect polices the KLV walk.
# A rung is 12% wide, and the worst of the three measured values sits 1.8% off.
STOPS = [1.0, 1.1, 1.2, 1.4, 1.6, 1.8, 2.0, 2.2, 2.5, 2.8, 3.2, 3.5, 4.0, 4.5,
         5.0, 5.6, 6.3, 7.1, 8.0, 9.0, 10, 11, 13, 14, 16, 18, 20, 22]
STOP_TOLERANCE = 0.04


def f_number(raw):
    """Aperture from the encoded iris value, on the ladder the camera shows.

    Returns (f-number, relative distance from the exact decode to that rung). See
    LENS_TAGS for what anchors the formula.
    """
    exact = 2 ** ((raw - 32768) / 8192)
    nearest = min(STOPS, key=lambda s: abs(math.log(s / exact)))
    return nearest, abs(nearest - exact) / exact


def lens_series(path, duration, samples, head=None):
    """The lens tags at `samples` points across the clip, head and tail included.

    `head` is the already-parsed metadata of the first read, so listing a folder
    does not pay for the same seek twice.
    """
    # A body that writes no lens set at the head writes none anywhere -- it is a
    # per-frame set. Bail before the seeks, or every DJI clip in a folder pays for
    # eight reads that can only come back empty.
    if head is not None and not any(k in head for k in LENS_TAGS.values()):
        return []
    last = max(0.0, duration - 2)
    points = [last * i / (samples - 1) for i in range(samples)] if samples > 1 else [0.0]
    series = []
    for i, t in enumerate(points):
        meta = head if (i == 0 and head is not None) else parse_rtmd(
            read_rtmd(path, seconds=0.3, at=t))
        got = {k: meta[k] for k in LENS_TAGS.values() if k in meta}
        if got:
            series.append((t, got))
    return series


def lens_movement(series):
    """Per quantity: whether it moved, when it first did, and over what range.

    Reported and not judged -- a zoom mid-take is a choice, and only the caller
    knows whether this clip was meant to hold. `LENS_MOVE_FLOOR` says why the
    comparison is not simply for equality.
    """
    out = {}
    if not series:
        return out
    for group, tag_names in LENS_GROUPS.items():
        moved_at, span = None, {}
        for tag in tag_names:
            values = [(t, s[tag]) for t, s in series if tag in s]
            if not values:
                continue
            base = values[0][1]
            span[tag] = [min(v for _, v in values), max(v for _, v in values)]
            for t, v in values:
                if abs(v - base) > LENS_MOVE_FLOOR:
                    moved_at = t if moved_at is None else min(moved_at, t)
                    break
        if span:
            out[group] = {"moved": moved_at is not None, "at": moved_at,
                          "range": span}
    return out


def audio_silent(path):
    """True if every sample of the first audio track is zero.

    Sony disables audio recording in S&Q, so a silent track is a strong
    corroboration of slow motion -- and a warning that this clip cannot be
    synced by audio correlation.
    """
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-vn",
             "-af", "astats=measure_perchannel=Peak_level:measure_overall=none",
             "-f", "null", "-"], text=True).stderr
    peaks = re.findall(r"Peak level dB:\s*(-?[\d.]+|-inf)", r)
    if not peaks:
        return None
    return all(p == "-inf" for p in peaks)


def luma_stats(path, at=None):
    """YMIN/YMAX/SATAVG of one frame -- the empirical log-gamma check."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "info"]
    if at:
        cmd += ["-ss", str(at)]
    cmd += ["-i", path, "-vframes", "1", "-vf",
            "scale=640:-2,signalstats,metadata=print", "-f", "null", "-"]
    r = run(cmd, text=True).stderr
    g = lambda k: (float(m.group(1))
                   if (m := re.search(rf"signalstats\.{k}=(-?[\d.]+)", r)) else None)
    return {k: g(k) for k in ("YMIN", "YMAX", "YAVG", "SATAVG")}


def describe(path, verify=False, deep=False, lens=True):
    info = probe(path)
    rec = {"file": os.path.basename(path), "path": path}
    rec.update({k: info.get(k) for k in
                ("duration", "width", "height", "container_fps", "codec",
                 "pix_fmt", "color_range", "color_transfer", "timecode",
                 "audio_codec", "created_tag")})

    if "data_stream" not in info:
        rec["note"] = "no timed-metadata track (not a Sony XAVC clip?)"
        return rec

    meta = parse_rtmd(read_rtmd(path))
    rec.update(meta)
    if not meta.get("model_serial") and not meta.get("clock"):
        # A data track that is not Sony rtmd -- DJI, GoPro and others all write
        # their own. Nothing here can read those; say so rather than printing a
        # bare stanza that looks like a clip with no metadata.
        rec["note"] = ("timed-metadata track present but not Sony rtmd "
                       "-- no camera metadata to read")

    cap = meta.get("capture_fps")
    if cap and cap[1]:
        capture_fps = cap[0] / cap[1]
        rec["capture_fps"] = capture_fps
        cfps = info.get("container_fps") or 0
        if cfps:
            factor = capture_fps / cfps
            rec["slowmo_factor"] = round(factor, 4)
            rec["real_duration"] = info["duration"] / factor if factor else None
            rec["is_slowmo"] = abs(factor - 1.0) > 0.01
    sh = meta.get("shutter_s")
    if sh and sh[0]:
        rec["shutter"] = f"1/{sh[1]/sh[0]:.0f} s"
        # Shutter angle at capture, and at the rate you would deliver at.
        if rec.get("capture_fps"):
            rec["shutter_angle_capture"] = round(360 * (sh[0]/sh[1]) * rec["capture_fps"], 1)

    g = meta.get("master_gain_centidb")
    if g is not None:
        if g > 32767:                      # stored unsigned; negative gains wrap
            g -= 65536
        rec["master_gain_db"] = g / 100.0
        # ISO and gain are independent readings of the same thing, so their
        # agreement is a check that the tag mapping is still right.
        if rec.get("iso"):
            expected = 800 * 10 ** (rec["master_gain_db"] / 20)
            rec["iso_gain_agree"] = abs(expected - rec["iso"]) / rec["iso"] < 0.06

    # The imager should come out at the sensor's real aspect; if it does not,
    # the KLV parse has drifted and nothing else here can be trusted.
    w, h = meta.get("imager_width_um"), meta.get("imager_height_um")
    if w and h:
        rec["imager_mm"] = f"{w/1000:.2f} x {h/1000:.2f}"
        rec["imager_aspect"] = round(w / h, 4)
        rec["parse_ok"] = abs(w / h - 16 / 9) < 0.01 or abs(w / h - 3 / 2) < 0.01

    # Head and tail whenever the lens is being asked about, because a rack that
    # happened at all usually shows in the two ends; --deep spreads eight samples
    # over the take, which is what catches focus that moved and moved back. A
    # caller that only wants the clock passes lens=False and pays for neither.
    series = lens_series(path, info["duration"], 8 if deep else 2,
                         head=meta) if lens else []
    if series:
        rec["lens_samples"] = len(series)
        rec["lens"] = lens_movement(series)
        if "iris_f_raw" in series[0][1]:
            rec["aperture"], fit = f_number(series[0][1]["iris_f_raw"])
            rec["aperture_on_ladder"] = fit <= STOP_TOLERANCE

    if deep or verify:
        rec["audio_silent"] = audio_silent(path)
        rec["luma"] = luma_stats(path, at=min(60, info["duration"] / 3))
        y = rec["luma"]
        if y.get("YMAX") is not None:
            # S-Log3 black sits at 95/1023 == 24/255 full-range, and the curve
            # never reaches white; ordinary Rec.709 material runs to ~255.
            rec["looks_like_log"] = y["YMAX"] < 200 and (y.get("SATAVG") or 99) < 8

    if verify and rec.get("clock"):
        tail = parse_rtmd(read_rtmd(path, from_end=True, duration=info["duration"]))
        rec["clock_end"] = tail.get("clock")
        if rec["clock_end"]:
            import datetime
            f = "%Y-%m-%d %H:%M:%S"
            a = datetime.datetime.strptime(rec["clock"], f)
            b = datetime.datetime.strptime(rec["clock_end"], f)
            elapsed = (b - a).total_seconds()
            if elapsed > 0:
                rec["measured_factor"] = round(info["duration"] / elapsed, 3)
    return rec


