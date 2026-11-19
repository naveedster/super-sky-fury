#!/bin/sh
# ringcmp.sh projdir tag DEFINES... : RING build of projdir/src, per-frame load stats for sa0/1/2 (snes9x)
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
P=$1; T=$2; shift 2
D=""; for d in RING "$@"; do D="$D -D $d"; done
cd $P && ca65 -g --cpu 65816 -I src $D -o /tmp/rc_$T.o src/main.s && ld65 -C src/lorom.cfg -o /tmp/rc_$T.sfc /tmp/rc_$T.o && python3 "$ROOT/tools/fixchecksum.py" /tmp/rc_$T.sfc >/dev/null
cd "$ROOT"
for s in 0 1 2; do
  WRAMDUMP=/tmp/rc_${T}_$s.wram ./tools/lrharness tools/cores/snes9x_libretro.so /tmp/rc_$T.sfc tools/dev/sa$s.txt /tmp/rc_out >/dev/null 2>&1
  echo "$T sa$s: $(python3 tools/dev/ring.py /tmp/rc_${T}_$s.wram 5400)"
done
