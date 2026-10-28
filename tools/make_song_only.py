#!/usr/bin/env python3
"""Build the song-only sing-along video for an episode folder.

Usage: python3 make_song_only.py ep03
Reads epNN/epNN.json (song + song_scenes) and the memory line from
../eliora-repo/episodes.json, writes "epNN/<Title> - Song - Eliora.mp4".
"""
import json, os, subprocess, sys

ep = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
d = os.path.join(here, ep)
c = json.load(open(os.path.join(d, f"{ep}.json")))
n = int(ep[2:])
memory = ""
try:
    for e in json.load(open(os.path.join(here, "..", "eliora-repo", "episodes.json")))["episodes"]:
        if e["n"] == n:
            memory = e.get("memory_line", "")
except Exception:
    pass

# Keep scene order, drop duplicates; open on the family singing.
scenes = []
for s in c["song_scenes"]:
    if s not in scenes:
        scenes.append(s)

out = f"{c['title']} - Song - Eliora.mp4"
cmd = ["python3", os.path.join(here, "build_song_video.py"), "--song", c["song"],
       "--scenes", *scenes, "--title", c["title"], "--subtitle", c.get("subtitle", ""),
       "--memory", memory, "--out", out]
subprocess.run(cmd, cwd=d, check=True)
print(os.path.join(d, out))
