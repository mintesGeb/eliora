#!/bin/bash
# usage: prep_narration.sh raw.wav out.wav
# Evens out the narrator: removes the slow drift to quiet/deep, lifts pitch slightly, keeps constant loudness.
set -e
ffmpeg -y -loglevel error -i "$1" -af "highpass=f=90,rubberband=pitch=1.06,equalizer=f=2800:t=q:w=1.2:g=3,equalizer=f=180:t=q:w=1:g=-3,dynaudnorm=f=150:g=15:p=0.9:m=20:s=8,acompressor=threshold=-20dB:ratio=3:attack=10:release=200,loudnorm=I=-16:TP=-1.5:LRA=7" -ar 44100 "$2"
