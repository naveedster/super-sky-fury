#!/bin/sh
# Measures main-loop speed per view: loops vs NMIs (60 = full rate) and worst scanline reached.
cd "$(dirname "$0")/.."
core=${1:-snes9x}
L=$(grep " .loops$" build/snesfly.lbl | cut -c6-9); M=$(grep " .maxline$" build/snesfly.lbl | cut -c6-9)
# input starts at frame 130: the APU upload takes ~1 s at boot
for n in 0 1 2; do
  s=/tmp/perf$n.txt; : > $s
  f=130; i=0; while [ $i -lt $n ]; do echo "$f hold SELECT" >> $s; echo "$((f+2)) hold none" >> $s; f=$((f+10)); i=$((i+1)); done
  echo "200 hold RIGHT,B" >> $s; echo "400 hold LEFT,UP" >> $s; echo "600 hold R,DOWN" >> $s; echo "800 end" >> $s
  printf "view %s: " $n
  PEEK=0,$L,$M ./tools/lrharness tools/cores/${core}_libretro.so build/snesfly.sfc $s /tmp | grep peek | awk '{printf "%s ", $4}'; echo "(nmi loops maxline)"
done
