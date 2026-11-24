#!/bin/sh
# make_voice.sh : TTS (edge-tts, en-US-ChristopherNeural) -> deep, compressed 9 kHz mono voice line
# -> music/dad_voice.wav (committed; music/make_boss.py BRR-encodes it into the boss ARAM image)
set -e
T=/tmp/dadvoice; mkdir -p $T
edge-tts --voice en-US-ChristopherNeural --rate=+4% --pitch=-14Hz --text "Naveed! I will destroy you!" --write-media $T/raw.mp3
ffmpeg -v error -y -i $T/raw.mp3 -ac 1 -ar 44100 $T/raw.wav
python3 -c "
import wave,numpy as np
w=wave.open('$T/raw.wav'); x=np.frombuffer(w.readframes(w.getnframes()),np.int16)
e=np.abs(x)>600; i=np.argmax(e); j=len(x)-np.argmax(e[::-1])
o=wave.open('$T/trim.wav','wb'); o.setnchannels(1); o.setsampwidth(2); o.setframerate(44100); o.writeframes(x[max(0,i-200):j+800].tobytes())"
ffmpeg -v error -y -i $T/trim.wav \
  -af "asetrate=44100*0.93,aresample=44100,atempo=1.2,\
highpass=f=90,lowpass=f=4200,equalizer=f=180:t=q:w=1.0:g=4,equalizer=f=2600:t=q:w=1.2:g=5,\
acompressor=threshold=-20dB:ratio=5:attack=4:release=60:makeup=6,alimiter=limit=0.95,\
aresample=9000:resampler=soxr,apad=pad_dur=0.06" -ar 9000 -c:a pcm_s16le music/dad_voice.wav
ffprobe -v error -show_entries format=duration -of csv=p=0 music/dad_voice.wav
