#!/usr/bin/env python3
"""Eliora v2 episode builder.

Layout: [porch bumper + brand card] [title card] [story, clean] [song x2 with karaoke lyrics] [porch end loop]
Also writes <out>.srt (story captions, timed to the final video) and <out>.lyrics.ass is burned in.
Config = same JSON as build_episode.py, plus optional: "lyrics": "lyrics.txt", "story_text": "narration.txt".
Usage: build_v2.py config.json [--no-bumper]
"""
import json, os, re, subprocess, sys, tempfile, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")
spec = importlib.util.spec_from_file_location("v1", os.path.join(HERE, "build_episode.py"))
v1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v1)
W, H, FPS = 1920, 1080, 30
BOLD = os.path.join(ASSETS, "Poppins-Bold.ttf"); MED = os.path.join(ASSETS, "Poppins-Medium.ttf")
NAVY, GOLD, CREAM = (38, 36, 78), (255, 196, 61), (255, 246, 226)


def run(cmd): return v1.run(cmd)
def dur(p): return v1.dur(p)


def fit(draw, text, font_path, size, maxw):
    while size > 30:
        f = ImageFont.truetype(font_path, size)
        if draw.textlength(text, font=f) <= maxw: return f
        size -= 4
    return ImageFont.truetype(font_path, 30)


def brand_card(path):
    im = Image.new("RGB", (W, H), CREAM)
    g = Image.new("RGB", (W, H)); px = np.zeros((H, W, 3), np.uint8)
    for y in range(H):
        t = y / H; px[y, :] = [int(255 - 25 * t), int(240 - 50 * t), int(205 - 70 * t)]
    im = Image.fromarray(px)
    logo = Image.open(os.path.join(HERE, "..", "branding", "profile.png")).convert("RGB").resize((420, 420))
    m = Image.new("L", (420, 420), 0); ImageDraw.Draw(m).ellipse((0, 0, 419, 419), fill=255)
    im.paste(logo, (W // 2 - 210, 150), m)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(BOLD, 150); d.text((W // 2, 680), "Eliora", font=f, fill=NAVY, anchor="mm", stroke_width=4, stroke_fill=GOLD)
    f2 = ImageFont.truetype(MED, 58); d.text((W // 2, 830), "God is my light", font=f2, fill=(120, 80, 30), anchor="mm")
    im.save(path)


def title_card(c, scene, path):
    """Left: title panel (never over faces). Right: story art."""
    im = Image.new("RGB", (W, H), CREAM)
    px = np.zeros((H, W, 3), np.uint8)
    for x in range(W):
        t = x / W; px[:, x] = [int(255 - 10 * t), int(240 - 30 * t), int(205 - 50 * t)]
    im = Image.fromarray(px)
    art = Image.open(scene).convert("RGB")
    aw, ah = 1020, 930
    s = max(aw / art.width, ah / art.height); art = art.resize((int(art.width * s), int(art.height * s)))
    l, t = (art.width - aw) // 2, (art.height - ah) // 2; art = art.crop((l, t, l + aw, t + ah))
    mask = Image.new("L", (aw, ah), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, aw - 1, ah - 1), 56, fill=255)
    sh = Image.new("RGBA", (aw + 80, ah + 80), (0, 0, 0, 0)); ImageDraw.Draw(sh).rounded_rectangle((40, 50, aw + 40, ah + 50), 56, fill=(60, 30, 0, 110))
    sh = sh.filter(ImageFilter.GaussianBlur(22)); im.paste(sh, (W - aw - 70 - 40, 70 - 40), sh)
    im.paste(art, (W - aw - 70, 70), mask)
    d = ImageDraw.Draw(im)
    logo = Image.open(os.path.join(HERE, "..", "branding", "profile.png")).convert("RGB").resize((130, 130))
    m = Image.new("L", (130, 130), 0); ImageDraw.Draw(m).ellipse((0, 0, 129, 129), fill=255); im.paste(logo, (80, 80), m)
    d.text((235, 145), "Eliora", font=ImageFont.truetype(BOLD, 62), fill=NAVY, anchor="lm")
    d.text((235, 200), "Bible stories for kids", font=ImageFont.truetype(MED, 30), fill=(120, 80, 30), anchor="lm")
    # Title, wrapped to the panel width
    words, lines, cur, fnt = c["title"].split(), [], "", ImageFont.truetype(BOLD, 128)
    for w in words:
        trial = (cur + " " + w).strip()
        if d.textlength(trial, font=fnt) > 700 and cur: lines.append(cur); cur = w
        else: cur = trial
    lines.append(cur)
    fs = 128
    while max(d.textlength(l_, font=ImageFont.truetype(BOLD, fs)) for l_ in lines) > 740: fs -= 6
    fnt = ImageFont.truetype(BOLD, fs); y = 470 - (len(lines) * fs * 1.12) / 2
    for l_ in lines:
        d.text((90, y), l_, font=fnt, fill=NAVY, stroke_width=7, stroke_fill=GOLD); y += fs * 1.12
    if c.get("subtitle"):
        sf = fit(d, c["subtitle"], BOLD, 50, 620); tw = d.textlength(c["subtitle"], font=sf)
        by = y + 30; d.rounded_rectangle((90, by, 90 + tw + 70, by + 100), 50, fill=NAVY)
        d.text((125, by + 50), c["subtitle"], font=sf, fill=(255, 255, 255), anchor="lm")
    d.text((90, 940), "with Grandpa Sol, Eli, Zara and Pip", font=ImageFont.truetype(MED, 38), fill=(120, 80, 30), anchor="lm")
    im.save(path)


def still_clip(img, secs, out, fade=0.5, zoom=True):
    frames = int(secs * FPS)
    z = f"1+0.04*on/{frames}" if zoom else "1"
    vf = (f"scale={W*2}:{H*2},zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
          f"fade=t=in:st=0:d={fade},fade=t=out:st={secs-fade}:d={fade},format=yuv420p")
    run(["ffmpeg", "-y", "-loop", "1", "-i", img, "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-vf", vf,
         "-frames:v", str(frames), "-t", str(secs), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
         "-c:a", "aac", "-b:a", "192k", "-shortest", out])


def norm_video(src, out, vf_extra="", t=None):
    vf = f"scale={W}:{H}:flags=lanczos,fps={FPS},format=yuv420p{vf_extra}"
    cmd = ["ffmpeg", "-y", "-i", src, "-vf", vf, "-af", "aresample=48000,aformat=channel_layouts=stereo"]
    if t: cmd += ["-t", str(t)]
    run(cmd + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", out])


def make_bumper(tmp):
    src = os.path.join(ASSETS, "bumper_porch.mp4"); a = os.path.join(tmp, "b_a.mp4"); br = os.path.join(tmp, "b_card.png")
    brand_card(br)
    run(["ffmpeg", "-y", "-i", src, "-vf", f"scale={W}:{H}:flags=lanczos,fps={FPS},format=yuv420p,fade=t=in:st=0:d=0.4",
         "-af", "aresample=48000,aformat=channel_layouts=stereo,volume=0.8,afade=t=out:st=3.4:d=0.8", "-t", "4.2",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", a])
    b = os.path.join(tmp, "b_b.mp4"); still_clip(br, 2.4, b, fade=0.5, zoom=False)
    return [a, b]


def make_endloop(tmp, secs=16):
    src = os.path.join(ASSETS, "bumper_porch.mp4"); f = os.path.join(tmp, "e_f.mp4"); r = os.path.join(tmp, "e_r.mp4")
    norm_video(src, f)
    run(["ffmpeg", "-y", "-i", f, "-vf", "reverse", "-af", "areverse", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", r])
    lst = os.path.join(tmp, "e.txt"); open(lst, "w").write("".join(f"file '{p}'\n" for p in [f, r, f, r]))
    out = os.path.join(tmp, "e_loop.mp4")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-t", str(secs),
         "-vf", f"fade=t=in:st=0:d=0.5,fade=t=out:st={secs-1.5}:d=1.5", "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={secs-1.5}:d=1.5",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "aac", "-b:a", "192k", out])
    return out


# ---------- lyrics timing (estimated from the song's energy) ----------
def syl(word):
    w = re.sub(r"[^a-z]", "", word.lower())
    return max(1, len(re.findall(r"[aeiouy]+", w)) - (1 if w.endswith("e") and len(w) > 3 and not w.endswith("le") else 0))


def envelope(song):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", song, "-ac", "1", "-ar", "16000", "-af", "highpass=f=250,lowpass=f=3500",
                          "-f", "f32le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.float32); hop = 1600  # 0.1 s
    n = len(x) // hop
    return 20 * np.log10(np.sqrt((x[: n * hop].reshape(n, hop) ** 2).mean(axis=1)) + 1e-6)


def parse_lyrics(path):
    sections, cur = [], []
    for ln in open(path, encoding="utf-8").read().splitlines():
        ln = ln.strip()
        if ln.startswith("[") or not ln:
            if cur: sections.append(cur); cur = []
            continue
        cur.append(ln)
    if cur: sections.append(cur)
    return sections


def lyric_events(song, lyrics_path):
    import lyric_align
    secs = parse_lyrics(lyrics_path)
    times = lyric_align.fit_sections(song, secs)
    lines = [ln for s in secs for ln in s]
    return [(a, b, ln) for (a, b), ln in zip(times, lines)], times[0][0]


def ass_time(t):
    h, m, s = int(t // 3600), int(t % 3600 // 60), t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def build_ass(path, passes, tail_badge):
    """passes: list of (offset, events). Karaoke fill per word, weighted by syllables."""
    hdr = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Lyric,Poppins,92,&H003DC4FF,&H00FFFFFF,&H004E2426,&H96000000,-1,0,0,0,100,100,0,0,1,8,3,2,60,60,64,1
Style: Badge,Poppins,44,&H00FFFFFF,&H00FFFFFF,&H004E2426,&HC84E2426,-1,0,0,0,100,100,0,0,3,10,0,9,0,50,50,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    out = [hdr]
    for off, ev in passes:
        for s0, e0, ln in ev:
            words = ln.split(); ws = [syl(x) for x in words]; tot = sum(ws); span = (e0 - s0) * 0.92
            k = "".join(f"{{\\kf{max(int(span * 100 * x / tot), 1)}}}{wd} " for wd, x in zip(words, ws))
            out.append(f"Dialogue: 0,{ass_time(off + s0)},{ass_time(off + e0 + 0.1)},Lyric,,0,0,0,,{{\\fad(150,150)}}{k.strip()}\n")
    for s0, e0, txt in tail_badge:
        out.append(f"Dialogue: 1,{ass_time(s0)},{ass_time(e0)},Badge,,0,0,0,,{{\\fad(200,300)}}{txt}\n")
    open(path, "w", encoding="utf-8").write("".join(out))


def story_srt(path, text_path, bounds, offset):
    paras = [p.strip() for p in open(text_path, encoding="utf-8").read().split("\n\n") if p.strip()]
    def stamp(t):
        ms = int(round(t * 1000)); return f"{ms//3600000:02d}:{ms//60000%60:02d}:{ms//1000%60:02d},{ms%1000:03d}"
    out, n = [], 1
    for p, (a, b) in zip(paras, zip(bounds[:-1], bounds[1:])):
        sents = re.findall(r"[^.!?]+[.!?\"”]*(?:\s|$)", p) or [p]
        sents = [s.strip() for s in sents if s.strip()]
        tot = sum(len(s) for s in sents); t = a
        for s in sents:
            d = (b - a) * len(s) / tot
            out.append(f"{n}\n{stamp(offset + t)} --> {stamp(offset + t + d - 0.05)}\n{s}\n"); n += 1; t += d
    open(path, "w", encoding="utf-8").write("\n".join(out))


def main(cfg_path, bumper=True):
    c = json.load(open(cfg_path)); base = os.path.dirname(os.path.abspath(cfg_path)); P = lambda p: os.path.join(base, p)
    c2 = dict(c); c2["_clean"] = True
    with tempfile.TemporaryDirectory() as tmp:
        # 1) clean main video (no text overlays) via v1 pieces
        main_cfg = dict(c, out="_main_clean.mp4", title="", subtitle="", end_text="", channel="")
        mc = os.path.join(base, "_main_cfg.json"); json.dump(main_cfg, open(mc, "w"))
        src = open(os.path.join(HERE, "build_episode.py")).read()
        # run v1 with overlays disabled by env flag
        os.environ["ELIORA_CLEAN"] = "1"
        if not (os.environ.get("ELIORA_REUSE") and os.path.exists(P("_main_clean.mp4"))):
            v1.main(mc)
        clean = P("_main_clean.mp4"); n_len, s_len = dur(P(c["narration"])), dur(P(c["song"])); gap = 0.8
        pre = []
        if bumper: pre += make_bumper(tmp)
        tcard = os.path.join(tmp, "title.png"); title_card(c, P(c["paragraph_scenes"][0][0]), tcard)
        t_clip = os.path.join(tmp, "title.mp4"); still_clip(tcard, 3.6, t_clip); pre.append(t_clip)
        pre_len = sum(dur(p) for p in pre)
        # 2) lyrics (karaoke) over the song passes
        song_start = n_len + gap; reps = c.get("song_repeats", 2)
        ev, on = lyric_events(P(c["song"]), P(c["lyrics"]))
        passes = [(song_start + r * s_len, ev) for r in range(reps)]
        badges = [(song_start + 0.3, song_start + 4, "Let's sing!"), (song_start + s_len + 0.3, song_start + s_len + 4, "Sing along with Eli and Pip!")]
        ass = os.path.join(tmp, "lyrics.ass"); build_ass(ass, passes, badges)
        body = os.path.join(tmp, "body.mp4")
        run(["ffmpeg", "-y", "-i", clean, "-vf", f"subtitles={ass}:fontsdir={ASSETS}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "copy", body])
        body_n = os.path.join(tmp, "body_n.mp4"); norm_video(body, body_n)
        parts = pre + [body_n, make_endloop(tmp)]
        ins = sum([["-i", p] for p in parts], [])
        fc = "".join(f"[{i}:v]setsar=1[sv{i}];" for i in range(len(parts))) + "".join(f"[sv{i}][{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=1:a=1[v][a]"
        out = P(c["out"])
        run(["ffmpeg", "-y"] + ins + ["-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out])
        if c.get("story_text"):
            w = c.get("paragraph_weights"); tot = n_len
            if w:
                acc = 0; bounds = [0.0]
                for x in w: acc += x; bounds.append(tot * acc / sum(w))
            else: bounds = v1.paragraph_breaks(P(c["narration"]), len(c["paragraph_scenes"]))
            story_srt(out.replace(".mp4", ".srt"), P(c["story_text"]), bounds, pre_len)
        os.remove(clean); os.remove(mc)
        print(f"Built {out}: {dur(out)/60:.1f} min; story captions offset {pre_len:.1f}s; lyrics start ~{on:.1f}s into song")


if __name__ == "__main__":
    main(sys.argv[1], "--no-bumper" not in sys.argv)
