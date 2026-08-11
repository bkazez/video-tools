# Two presets for the ZV-E10 II: cinematic 4K, Europe and US

For the shoot itself, open `camera-card.html` beside this file — same settings,
no reasoning. This page is the why.

Highest quality this body can record, set up so the only thing you decide on the
day is which region you are in.

## Step 0: the switch, every single time

The **Still / Movie / S&Q switch** is a physical control. If it is on S&Q you get
2x slow motion and **no audio at all**
([Sony](https://helpguide.sony.net/ilc/2430/v1/en/contents/0412L_s_q_settings.html)),
and no saved preset can override it. That is what happened on 2026-04-07: sixteen
clips, all silent, all 2x, and the sync had to be rebuilt by hand.

**Movie. Look at it. Then start.**

## Step 1: region, before you recall anything

    MENU -> Setup -> Area/Date -> NTSC/PAL Selector

- **Europe / UK -> PAL** (gives 25p / 50p)
- **US -> NTSC** (gives 24p / 30p / 60p)

Source: [NTSC/PAL Selector](https://helpguide.sony.net/ilc/2430/v1/en/contents/0601_pal_ntsc_select.html).
This is **not** stored in Camera Set. Memory, so it is always the first move. Sony
bodies commonly want to format the card when this changes — offload first.

## Step 2: the two presets

| | Europe / UK | US |
|---|---|---|
| NTSC/PAL Selector | PAL | NTSC |
| File Format | XAVC S 4K | XAVC S 4K |
| Record Setting | **25p 140M 4:2:2 10-bit** | **24p 100M 4:2:2 10-bit** |
| Shutter speed | **1/50** (180°) | **1/60** (144°) |
| …if the light is daylight or flicker-free LED only | 1/50 | 1/48 (180°) |
| Exposure mode | Manual | Manual |
| ISO | 800, or 2500 in low light | 800, or 2500 in low light |
| Picture Profile | S-Log3 / S-Gamut3.Cine | S-Log3 / S-Gamut3.Cine |
| White balance | manual Kelvin | manual Kelvin |
| Focus Mode | Manual Focus, AF on a held button | Manual Focus, AF on a held button |

Record Setting bit rates and depths are from Sony's
[Movie Settings table](https://helpguide.sony.net/ilc/2430/v1/en/contents/0412B_movie_setting.html):
XAVC S 4K carries 4:2:2 10-bit at 140M for 25p/30p, 100M for 24p, 200M for 50p/60p.

Two things worth knowing about those choices:

- **25p is both the flicker-correct and the higher-bitrate option in Europe** —
  140M against 24p's 100M.
- **The codec costs nothing to edit.** 4K 10-bit 4:2:2 H.264 decodes at 35 fps in
  software on the M4 Max (150 frames in 4.2 s, measured 2026-08-10), so there is no
  reason to record anything lower for the sake of the edit.

### Why the US shutter is not 1/48

Mains light flickers at twice mains frequency. The exposure has to be a whole
number of flicker periods or the picture bands.

| region | flicker | period | 180° shutter at the film rate | whole periods? |
|---|---|---|---|---|
| Europe, 50 Hz | 100 Hz | 10 ms | 25p -> 1/50 = 20 ms | **yes, exactly 2** |
| US, 60 Hz | 120 Hz | 8.33 ms | 24p -> 1/48 = 20.8 ms | **no, 2.5 — it bands** |

At 24p under 60 Hz light the safe shutters are 1/60 (16.67 ms, 144°) and 1/40
(25 ms, 216°). Both sit 36° from 180, in opposite directions. 1/60 is the
convention, so that is the preset.

If you would rather run one cadence in both regions, 24p at **1/50** in Europe is
flicker-safe and 172.8°, which is near enough to 180 to be invisible — check
whether 24p appears in the Record Setting list while the selector is on PAL, since
that varies by body.

## Step 3: everything else, identical in both presets

- **Manual exposure.** Auto shutter is what produced 89° and 70° clips on
  2026-06-20 — visibly staccato motion. Lock the shutter and it cannot drift.
- **Fixed ISO, not Auto.** S-Log3 on this sensor has **dual base ISO 800 and 2500**
  ([reported](https://www.photographyblog.com/reviews/sony_zv_e10_ii_review)), so
  those two are the clean stops: 2500 is cleaner than 1600. Above 2500 the grade
  starts fighting grain, which was the limit on 2026-04-07.
- **S-Log3, and expose it brighter than feels right.** On 2026-04-07 lit skin landed
  at 35% of full through the standard log conversion, so the grade had to lift it
  about 1.8x and the grain came with it. Turn **Gamma Disp. Assist** on (S-Log3 ->
  709) so the screen is watchable, and put lit skin at **60-70%**. That is the
  target the grade aims for anyway, so giving it to the camera is free.
  S-Cinetone is the alternative if you ever want to skip grading entirely; set
  `log: "no"` in the matching profile if you do.
- **Manual white balance in Kelvin, not AWB.** Locked WB is what lets one grade
  cover a whole session.
- **Record audio even though the real audio is on the recorder.** It is the sync
  reference. Losing it is what cost hours on 2026-04-07.

## Step 3b: focus, for a shot you are not standing behind

The problem is specific: a stand-in holds the position, focus is set on them, and
then the person in frame is the one who cannot see the screen. Nothing may pull
focus for the next twenty minutes.

**Movie mode gives no focus mode that does this.** Only Continuous AF and Manual
Focus are offered while the switch is on Movie
([Focus Mode](https://helpguide.sony.net/ilc/2430/v1/en/contents/0405C_focus_mode.html)) —
there is no AF-S to acquire once and stop. Continuous AF with the transition speed
slowed still refocuses; it only takes longer about it.

**So the resting state is Manual Focus, and AF is a button.** This body will
autofocus out of MF, but only for movie:

> When shooting a movie, you can perform auto-focusing by holding down the custom
> key to which [AF On] is assigned even in the manual focusing mode.
> — [AF On](https://helpguide.sony.net/ilc/2430/v1/en/contents/0405_af_on.html)

That is the whole answer. In MF there is no mechanism that can refocus, and the
button is the only thing that ever moves it.

    MENU -> Focus -> AF/MF -> Focus Mode -> Manual Focus
    MENU -> Setup -> Operation Customize -> Custom Key/Dial Set. -> C1 -> AF On
    MENU -> Setup -> Operation Customize -> Custom Key/Dial Set. -> centre -> Focus Magnifier

Custom keys are held **separately per shooting mode**, so the movie assignment has
to be made with the switch on Movie
([Custom Key/Dial Set.](https://helpguide.sony.net/ilc/2430/v1/en/contents/0413M_custom_key.html)).
Focus Magnifier works in MF and during movie recording
([Focus Magnifier](https://helpguide.sony.net/ilc/2430/v1/en/contents/0405_focus_magni.html)),
which is what the check on the stand-in uses. Turn **Peaking Display** on beside it.

Three things then have to be off, because each one exists to move focus:

- **Product Showcase Set** — pulls focus to whatever is held toward the lens.
- **Touch operation** — a touch on the screen starts tracking, and the screen gets
  touched while a camera is being positioned.
- **The lens's own AF/MF switch, if it has one, stays on AF.** The lens overrides
  the body, and MF on the lens takes AF On down with it
  ([AF/MF Selector](https://helpguide.sony.net/ilc/2430/v1/en/contents/0405_af_mf_control.html)).

On the day: frame, **then** focus. Hold C1 until it settles on the stand-in,
release, press the centre button and magnify to confirm. Re-do it after any power
cycle, since a power zoom retracts when the body powers off and does not come back
where it was.

**Zoom is what breaks this, not focus.** On 2026-04-07 every clip whose zoom ring
moved also moved focus — C0488, C0491, C0496 and C0497, measured from their own
lens metadata (`sony-clip-info --deep`). The kit power zoom is not parfocal, so
reframing by zoom after focusing throws away the focus.

## Step 3c: prove it, from the clip

The lens writes its aperture, focus and zoom into the clip's metadata track every
frame, so "nothing refocused" is a reading rather than a memory:

    sony-clip-info --deep Video/C0489.MP4

    aperture          f/3.2, held (8 samples identical)
    focus             held (8 samples identical)

`focus: locked` is asserted by both cinematic profiles, so the check that runs on
every card insert already covers it. Across the 16 clips of 2026-04-07 it holds ten
and fails six; C0492 racked focus 109 s in with the zoom untouched, and C0498
changed aperture from f/3.2 to f/5.6 mid-take. Zoom and aperture are reported and
not asserted — a zoom mid-take is a choice, not a fault.

## Step 4: register each preset in the camera

    MENU -> Shooting -> Shooting Mode -> Camera Set. Memory -> 1   (Europe)
    MENU -> Shooting -> Shooting Mode -> Camera Set. Memory -> 2   (US)

Set everything above first, then register. The body holds up to 3 memories **per
shooting mode**, plus M1-M4 on the card
([Sony](https://helpguide.sony.net/ilc/2430/v1/en/contents/0413_setting_memory.html)).

**Use the in-camera slots, not M1-M4.** Formatting a card erases the card ones, and
you reformat constantly.

Recall with **Recall Camera Set.** Region first (step 1), then recall.

## Step 5: back the whole configuration up off the card

    MENU -> Setup -> Reset/Save Settings -> Save/Load Settings -> Save New

That writes the entire configuration to the card
([Sony](https://helpguide.sony.net/ilc/2430/v1/en/contents/0601_save_load_settings.html)),
10 per card. **Formatting deletes it**, so copy the file off the card to keep it.
After a factory reset, copy it back and Load, instead of rebuilding by hand.

## Step 6: let the check tell you, so you do not have to remember

    camera-card-check --install-agent --expect profiles/sony-4k-cinematic-pal.yml
    camera-card-check --install-agent --expect profiles/sony-4k-cinematic-ntsc.yml

Whichever you install last is the one every inserted card is checked against, so
install the one for the region you are working in. By hand, any time:

    sony-clip-info --deep --expect profiles/sony-4k-cinematic-ntsc.yml CLIP.MP4

Both profiles assert resolution, bit depth, chroma, real-time (not S&Q), audio
present, frame rate, shutter angle and an ISO ceiling.
