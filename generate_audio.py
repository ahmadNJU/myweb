#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate the HSK 3 listening audio (audio/q1.mp3 .. audio/q40.mp3) from the
scripts in hsk3-data.js, using free Microsoft neural voices via edge-tts.
No API key required. Three distinct voices (female / male / narrator) are used
so speakers are distinguishable, as in the real exam.

Usage:
    pip install edge-tts pydub imageio-ffmpeg
    python generate_audio.py            # only missing clips
    python generate_audio.py --force    # regenerate all
"""
import os, re, sys, json, asyncio

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "hsk3-data.js")
OUT  = os.path.join(HERE, "audio")
FORCE = "--force" in sys.argv

# Distinct voices; slight slow-down suits HSK 3 listening.
VOICE = {"f": "zh-CN-XiaoxiaoNeural",   # female speaker
         "m": "zh-CN-YunxiNeural",      # male speaker
         "n": "zh-CN-XiaoyiNeural"}     # narrator (the 问 question)
RATE  = "-8%"
GAP_MS = 450

def load_data():
    txt = open(DATA, encoding="utf-8").read()
    m = re.search(r"window\.HSK3\s*=\s*(\{.*\})\s*;?\s*$", txt, re.S)
    if not m:
        raise SystemExit("Could not parse hsk3-data.js")
    return json.loads(m.group(1))

def collect(data):
    """Return list of (n, [segments]) for every listening question."""
    items = []
    L = data["listening"]
    for g in L["part1"]["groups"]:
        for q in g["questions"]:
            items.append((q["n"], q["audio"]))
    for q in L["part2"]["questions"]:
        items.append((q["n"], q["audio"]))
    for q in L["part3"]["questions"]:
        items.append((q["n"], q["audio"]))
    for q in L["part4"]["questions"]:
        items.append((q["n"], q["audio"]))
    return items

# ---- audio backend: pydub (preferred, real silence gaps) or byte-concat fallback ----
def get_pydub():
    try:
        from pydub import AudioSegment
        try:
            import imageio_ffmpeg
            AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            pass
        return AudioSegment
    except Exception:
        return None

async def synth(text, voice, path):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=RATE).save(path)

async def build_one(n, segments, AudioSegment):
    tmp = []
    for i, s in enumerate(segments):
        p = os.path.join(OUT, f".seg_{n}_{i}.mp3")
        await synth(s["text"], VOICE.get(s["spk"], VOICE["n"]), p)
        tmp.append(p)
    final = os.path.join(OUT, f"q{n}.mp3")
    if AudioSegment:
        combined = AudioSegment.silent(duration=250)
        gap = AudioSegment.silent(duration=GAP_MS)
        for i, p in enumerate(tmp):
            combined += AudioSegment.from_file(p, format="mp3")
            if i != len(tmp) - 1:
                combined += gap
        combined.export(final, format="mp3")
    else:
        # fallback: concatenate MP3 bytes (browsers tolerate this)
        with open(final, "wb") as out:
            for p in tmp:
                out.write(open(p, "rb").read())
    for p in tmp:
        try: os.remove(p)
        except OSError: pass
    return final

async def main():
    os.makedirs(OUT, exist_ok=True)
    data = load_data()
    items = collect(data)
    AudioSegment = get_pydub()
    if AudioSegment is None:
        print("[note] pydub/ffmpeg not found — using MP3 byte-concatenation fallback "
              "(works in browsers; install pydub+imageio-ffmpeg for cleaner gaps).")
    made = skipped = 0
    for n, segs in items:
        target = os.path.join(OUT, f"q{n}.mp3")
        if os.path.exists(target) and not FORCE:
            skipped += 1; continue
        print(f"  q{n}: {len(segs)} segment(s) -> {os.path.basename(target)}")
        await build_one(n, segs, AudioSegment)
        made += 1
    print(f"Done. Generated {made}, skipped {skipped}. Files in {OUT}/")

if __name__ == "__main__":
    asyncio.run(main())
