#!/bin/sh
# gfxshots.sh ROM outdir core : fixed screenshot set in all three views (same frames before/after)
cd "$(dirname "$0")/../.."
ROM=$1; OUT=$2; CORE=${3:-snes9x}; mkdir -p $OUT
mk(){ src=$1; shift; (grep -v end $src; for f in "$@"; do echo "$f shot $(basename $src .txt)_$f"; done; echo "$(( $(echo "$@" | tr ' ' '\n' | sort -n | tail -1) + 2 )) end") | sort -n -s -k1,1 > /tmp/gfx_$$.txt; ./tools/lrharness tools/cores/${CORE}_libretro.so $ROM /tmp/gfx_$$.txt $OUT >/dev/null 2>&1; }
mk tools/dev/sa0.txt 160 395 405 1060 1196 1570 4470
mk tools/dev/sa1.txt 300 822 1834 2000
mk tools/dev/sa2.txt 300 615 623 884 1378
rm -f /tmp/gfx_$$.txt
