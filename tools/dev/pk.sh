#!/bin/sh
# pk.sh core script var... -> name=value (16-bit WRAM peeks by label); OUTD=shot dir, ROM=rom
cd "$(dirname "$0")/../.."
core=$1; scr=$2; shift 2
ROM=${ROM:-build/snesfly.sfc}; OUTD=${OUTD:-/tmp/pkout}; mkdir -p $OUTD
A=""; for v in "$@"; do a=$(grep " \.$v\$" ${LBL:-build/snesfly.lbl} | head -1 | awk '{print $2}'); a=$(python3 -c "print('%x'%(0x$a & 0x1FFFF))"); A="$A,$a"; done
PEEK=${A#,} ./tools/lrharness tools/cores/${core}_libretro.so $ROM $scr $OUTD | grep "^peek" > /tmp/pk.$$
i=1; for v in "$@"; do val=$(sed -n "${i}p" /tmp/pk.$$ | awk '{print $4}'); printf "%s=%s " $v $val; i=$((i+1)); done; echo; rm -f /tmp/pk.$$
