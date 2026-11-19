#!/bin/sh
# quick variant build: qb.sh DEFINE...
cd "$(dirname "$0")/../.."
D=""; for d in "$@"; do D="$D -D $d"; done
ca65 -g --cpu 65816 -I src $D -o build/main.o src/main.s && ld65 -C src/lorom.cfg -o build/snesfly.sfc -m build/snesfly.map -Ln build/snesfly.lbl build/main.o && python3 tools/fixchecksum.py build/snesfly.sfc >/dev/null
