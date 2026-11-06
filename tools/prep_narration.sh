#!/bin/bash
# Gentle leveling only: no pitch shift, no EQ boost. Keeps the natural voice, just stops it fading/getting deep and quiet.
ffmpeg -y -loglevel error -i "$1" -af "highpass=f=80,dynaudnorm=f=250:g=11:p=0.9:m=10:s=8,acompressor=threshold=-22dB:ratio=2:attack=20:release=300,loudnorm=I=-16:TP=-1.5:LRA=9" -ar 44100 "$2"
