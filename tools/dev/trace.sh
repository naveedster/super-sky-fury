#!/bin/sh
# trace.sh core script out.txt var... : per-frame values of labels (16-bit)
cd "$(dirname "$0")/../.."
core=$1; scr=$2; out=$3; shift 3
A=""; for v in "$@"; do a=$(grep " \.$v\$" ${LBL:-build/snesfly.lbl} | head -1 | awk '{print $2}'); A="$A,$(python3 -c "print('%x'%(0x$a & 0x1FFFF))")"; done
echo "fr $*" > $out.hdr
TRACE=${A#,} TRACEOUT=$out ./tools/lrharness tools/cores/${core}_libretro.so ${ROM:-build/snesfly.sfc} $scr /tmp/trout >/dev/null
