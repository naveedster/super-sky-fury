#!/bin/sh
# usage: tools/shoot.sh <core> <script> <outdir>   -> PNGs (2x nearest)
set -e
cd "$(dirname "$0")/.."
core=$1; script=$2; out=$3
mkdir -p "$out"
./tools/lrharness tools/cores/${core}_libretro.so build/snesfly.sfc "$script" "$out"
for f in "$out"/*.ppm; do ffmpeg -v error -y -i "$f" -vf scale=iw*2:ih*2:flags=neighbor "${f%.ppm}.png" && rm "$f"; done
