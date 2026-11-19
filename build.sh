#!/bin/sh
# Build SUPER SKY FURY: regenerates assets, assembles, links, fixes the header checksum.
set -e
cd "$(dirname "$0")"
mkdir -p build
python3 tools/gen_assets.py assets
python3 tools/title_art.py assets
python3 tools/boss_fast.py
python3 music/make_music.py
python3 music/make_boss.py
(cd src && ca65 -g --cpu 65816 -I . -o ../build/main.o main.s)   # run from src/ so "../assets", "../music" resolve inside the repo
ld65 -C src/lorom.cfg -o build/snesfly.sfc -m build/snesfly.map -Ln build/snesfly.lbl build/main.o
python3 tools/fixchecksum.py build/snesfly.sfc
cp build/snesfly.sfc build/super_sky_fury.sfc
