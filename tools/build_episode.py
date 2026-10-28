#!/usr/bin/env python3
"""Eliora full-episode builder (story narration + sing-along song).

Episode layout:
  [Grandpa Sol narration over story scenes, scenes timed to paragraph pauses]
  [Song, first time, montage of song scenes]
  [Song, second time, "Sing along!" badge]
  End card text over the last seconds.

Config (JSON):
{
  "title": "...", "subtitle": "...", "channel": "Eliora",
  "narration": "narration.mp3",
  "paragraph_scenes": [["s1.jpg"], ["s2.jpg"], ["s9.jpg","s3.jpg"], ...],   # one list per paragraph
  "song": "song.mp3", "song_scenes": ["a.jpg", ...], "song_repeats": 2,
  "end_text": "Subscribe to Eliora for a new Bible story every week!",
  "out": "episode.mp4"
}
"""
import json, os, re, subprocess, sys, tempfile

FPS, W, H, XF = 30, 1920, 1080, 0.6
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.stderr.write(r.stderr[-3000:]); raise SystemExit("ffmpeg failed")
    return r


def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", p],
                       capture_output=True, text=True).stdout
    return float(json.loads(o)["format"]["duration"])


def esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace(",", "\\,")


def paragraph_breaks(audio, n_par):
    """Find the n_par-1 longest pauses in the narration -> paragraph boundaries."""
    r = subprocess.run(["ffmpeg", "-i", audio, "-af", "silencedetect=noise=-35dB:d=0.45", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    pairs = re.findall(r"silence_end: ([\d.]+) \| silence_duration: ([\d.]+)", r.stderr)
    ends = [float(e) for e, _ in pairs]
    durs = [float(d) for _, d in pairs]
    total = dur(audio)
    gaps = [((s + e) / 2, d) for s, e, d in zip(starts, ends, durs) if 3 < (s + e) / 2 < total - 2]
    # Take the longest pauses as paragraph breaks, then sort in time.
    best = sorted(sorted(gaps, key=lambda g: -g[1])[: n_par - 1])
    cuts = [g[0] for g in best]
    if len(cuts) < n_par - 1:  # fallback: even split
        cuts = [total * (i + 1) / n_par for i in range(n_par - 1)]
    return [0.0] + cuts + [total]


def clip(img, secs, idx, tmp):
    frames = max(int(round(secs * FPS)), 2)
    z = f"1+0.07*on/{frames}" if idx % 2 == 0 else f"1.07-0.07*on/{frames}"
    vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},format=yuv420p")
    out = os.path.join(tmp, f"c{idx:03d}.mp4")
    run(["ffmpeg", "-y", "-loop", "1", "-i", img, "-vf", vf, "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out])
    return out


def main(cfg_path):
    c = json.load(open(cfg_path))
    base = os.path.dirname(os.path.abspath(cfg_path))
    P = lambda p: os.path.join(base, p)
    narr, song = P(c["narration"]), P(c["song"])
    reps = c.get("song_repeats", 2)
    gap = 0.8
    pars = c["paragraph_scenes"]
    if c.get("paragraph_weights"):
        # Time each paragraph by its share of the words (steady narration pace).
        w = c["paragraph_weights"]; tot = dur(narr); acc = 0.0; bounds = [0.0]
        for x in w:
            acc += x; bounds.append(tot * acc / sum(w))
    else:
        bounds = paragraph_breaks(narr, len(pars))
    n_len, s_len = dur(narr), dur(song)

    # Visual timeline: (image, seconds). Each segment is lengthened by XF to absorb crossfade overlap.
    tl = []
    for i, scenes in enumerate(pars):
        span = bounds[i + 1] - bounds[i] + (gap if i == len(pars) - 1 else 0)
        for s in scenes:
            tl.append((P(s), span / len(scenes)))
    song_start = n_len + gap
    for r in range(reps):
        ss = c["song_scenes"] if r % 2 == 0 else list(reversed(c["song_scenes"]))
        for s in ss:
            tl.append((P(s), s_len / len(ss)))
    total = n_len + gap + reps * s_len
    tl = [(img, d + XF) for img, d in tl]
    tl[-1] = (tl[-1][0], tl[-1][1] - XF)

    with tempfile.TemporaryDirectory() as tmp:
        clips = [clip(img, d, i, tmp) for i, (img, d) in enumerate(tl)]
        # Concatenate in chunks of crossfades (filter graph per chunk keeps memory sane).
        def xfade_chain(paths, durs, out):
            ins, fc, last, off = [], [], "0:v", 0.0
            for p in paths: ins += ["-i", p]
            for i in range(1, len(paths)):
                off += durs[i - 1] - XF
                fc.append(f"[{last}][{i}:v]xfade=transition=fade:duration={XF}:offset={off:.3f}[x{i}]")
                last = f"x{i}"
            run(["ffmpeg", "-y"] + ins + ["-filter_complex", ";".join(fc) if fc else "[0:v]null[x0]",
                 "-map", f"[{last if fc else 'x0'}]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out])
        durs = [d for _, d in tl]
        video = os.path.join(tmp, "video.mp4")
        xfade_chain(clips, durs, video)

        # Audio: narration, gap, song x reps.
        audio = os.path.join(tmp, "audio.m4a")
        ins = ["-i", narr] + sum([["-i", song] for _ in range(reps)], [])
        parts = [f"[0:a]apad=pad_dur={gap}[n]"] + [f"[{i+1}:a]anull[s{i}]" for i in range(reps)]
        cat = "[n]" + "".join(f"[s{i}]" for i in range(reps)) + f"concat=n={reps+1}:v=0:a=1,loudnorm=I=-16:TP=-1.5[a]"
        run(["ffmpeg", "-y"] + ins + ["-filter_complex", ";".join(parts + [cat]), "-map", "[a]",
             "-c:a", "aac", "-b:a", "192k", audio])

        box = "box=1:boxcolor=0x00000066:boxborderw=26"
        clean = os.environ.get("ELIORA_CLEAN")
        t = [] if clean else [f"drawtext=fontfile={FONT}:text='{esc(c['title'])}':fontsize=92:fontcolor=white:x=(w-tw)/2:y=h*0.08:{box}:enable='lt(t,5)'",
             f"drawtext=fontfile={FONT}:text='{esc(c['channel'])}':fontsize=40:fontcolor=white@0.85:x=w-tw-48:y=h-th-40:shadowcolor=black@0.5:shadowx=2:shadowy=2"]
        if c.get("subtitle"):
            t.append(f"drawtext=fontfile={FONT}:text='{esc(c['subtitle'])}':fontsize=48:fontcolor=white:x=(w-tw)/2:y=h*0.08+130:{box}:enable='lt(t,5)'")
        t.append(f"drawtext=fontfile={FONT}:text='Let’s sing!':fontsize=80:fontcolor=white:x=(w-tw)/2:y=h*0.08:{box}:enable='between(t,{song_start:.2f},{song_start+4:.2f})'")
        if reps > 1:
            s2 = song_start + s_len
            t.append(f"drawtext=fontfile={FONT}:text='Sing along with Eli and Pip!':fontsize=64:fontcolor=white:x=(w-tw)/2:y=h*0.08:{box}:enable='between(t,{s2:.2f},{s2+6:.2f})'")
        if c.get("end_text"):
            t.append(f"drawtext=fontfile={FONT}:text='{esc(c['end_text'])}':fontsize=52:fontcolor=white:x=(w-tw)/2:y=h*0.08:{box}:enable='gte(t,{total-8:.2f})'")
        if clean: t = []
        t.append(f"fade=t=in:st=0:d=1,fade=t=out:st={total-1.5:.2f}:d=1.5")
        run(["ffmpeg", "-y", "-i", video, "-i", audio, "-filter_complex", "[0:v]" + ",".join(t) + "[v]",
             "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
             "-c:a", "copy", "-t", f"{total:.3f}", "-movflags", "+faststart", P(c["out"])])
    print(f"Built {c['out']}: {total/60:.1f} min, {len(tl)} shots; paragraph cuts at "
          + ", ".join(f"{b:.1f}" for b in bounds))


if __name__ == "__main__":
    main(sys.argv[1])
