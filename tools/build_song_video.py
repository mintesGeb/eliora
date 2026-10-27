#!/usr/bin/env python3
"""Eliora song-video builder.

Turns one song file + numbered scene images into a 1080p kids' sing-along video:
slow gentle zoom on each scene, soft crossfades, a title card, and an end card.

Usage:
  python3 build_song_video.py --song song.wav --scenes scene1.png scene2.png ... \
      --title "Little Stone, Big God" --subtitle "David and Goliath" \
      --memory "God is big, I am brave!" --out little_stone_big_god.mp4
"""
import argparse, json, subprocess, sys, tempfile, os

FPS = 30
W, H = 1920, 1080
XFADE = 0.8          # crossfade seconds between scenes
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-3000:])
        raise SystemExit(f"ffmpeg failed: {' '.join(cmd[:4])} ...")


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "json", path], capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


def esc(t):
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace(",", "\\,")


def scene_clip(img, secs, idx, tmp):
    """One scene with a slow zoom (alternating in/out) rendered to its own clip."""
    frames = int(round(secs * FPS))
    if idx % 2 == 0:   # zoom in 1.00 -> 1.08
        z = f"1+0.08*on/{frames}"
    else:              # zoom out 1.08 -> 1.00
        z = f"1.08-0.08*on/{frames}"
    vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
          f"zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},"
          f"format=yuv420p")
    out = os.path.join(tmp, f"s{idx:02d}.mp4")
    run(["ffmpeg", "-y", "-loop", "1", "-i", img, "-vf", vf, "-frames:v", str(frames),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--song", required=True)
    ap.add_argument("--scenes", nargs="+", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--memory", default="")
    ap.add_argument("--channel", default="Eliora")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    song_len = duration(a.song)
    n = len(a.scenes)
    # Each scene's on-screen length, accounting for crossfade overlaps, so the
    # video ends exactly when the song does.
    per = (song_len + XFADE * (n - 1)) / n

    with tempfile.TemporaryDirectory() as tmp:
        clips = [scene_clip(img, per, i, tmp) for i, img in enumerate(a.scenes)]

        # Chain crossfades.
        inputs, fc, last = [], [], "0:v"
        for c in clips:
            inputs += ["-i", c]
        offset = 0.0
        for i in range(1, n):
            offset += per - XFADE
            lab = f"x{i}"
            fc.append(f"[{last}][{i}:v]xfade=transition=fade:duration={XFADE}:offset={offset:.3f}[{lab}]")
            last = lab

        # Title card over the first 4 s, memory line over the last 5 s, fades at ends.
        box = "box=1:boxcolor=0x00000066:boxborderw=28"
        txt = [
            f"drawtext=fontfile={FONT}:text='{esc(a.title)}':fontsize=96:fontcolor=white:"
            f"x=(w-tw)/2:y=h*0.70:{box}:enable='lt(t,4)':alpha='if(lt(t,3),1,4-t)'",
        ]
        if a.subtitle:
            txt.append(f"drawtext=fontfile={FONT}:text='{esc(a.subtitle)}':fontsize=52:fontcolor=white:"
                       f"x=(w-tw)/2:y=h*0.83:enable='lt(t,4)':alpha='if(lt(t,3),1,4-t)'")
        txt.append(f"drawtext=fontfile={FONT}:text='{esc(a.channel)}':fontsize=40:fontcolor=white@0.85:"
                   f"x=w-tw-48:y=40:shadowcolor=black@0.5:shadowx=2:shadowy=2")
        end = song_len
        if a.memory:
            txt.append(f"drawtext=fontfile={FONT}:text='{esc(a.memory)}':fontsize=84:fontcolor=white:"
                       f"x=(w-tw)/2:y=h*0.12:{box}:enable='gte(t,{end-6:.2f})'")
        txt.append(f"fade=t=in:st=0:d=1,fade=t=out:st={end-1.2:.2f}:d=1.2")
        fc.append(f"[{last}]" + ",".join(txt) + "[v]")

        song_idx = len(clips)
        cmd = (["ffmpeg", "-y"] + inputs + ["-i", a.song, "-filter_complex", ";".join(fc),
               "-map", "[v]", "-map", f"{song_idx}:a",
               "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={end-1.5:.2f}:d=1.5",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "192k", "-t", f"{end:.3f}", "-movflags", "+faststart", a.out])
        run(cmd)
    print(f"Built {a.out}: {song_len:.1f}s, {n} scenes at {per:.1f}s each")


if __name__ == "__main__":
    main()
