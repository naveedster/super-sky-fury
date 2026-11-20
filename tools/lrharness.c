/* Minimal headless libretro frontend: runs a core + ROM with a scripted
 * joypad and dumps selected frames as PPM.
 * usage: lrharness core.so rom.sfc script.txt outdir
 * script lines:  <frame> hold <buttons>   (buttons: comma list or "none")
 *                <frame> shot <name>
 *                <frame> rec <name> <count> <step>   (dump count frames every step)
 *                <frame> end
 * buttons: B Y SELECT START UP DOWN LEFT RIGHT A X L R */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <dlfcn.h>
#include "libretro.h"

static unsigned pixfmt = RETRO_PIXEL_FORMAT_0RGB1555;
static unsigned held = 0;
static const void *lastfb; static unsigned lw, lh; static size_t lpitch;
static unsigned char *fbcopy;

static void log_cb(enum retro_log_level level, const char *fmt, ...) {
  if (!getenv("CORELOG")) return;
  va_list ap; va_start(ap, fmt); vfprintf(stderr, fmt, ap); va_end(ap);
}
static bool env_cb(unsigned cmd, void *data) {
  switch (cmd) {
  case RETRO_ENVIRONMENT_SET_PIXEL_FORMAT: pixfmt = *(unsigned*)data; return true;
  case RETRO_ENVIRONMENT_GET_SYSTEM_DIRECTORY:
  case RETRO_ENVIRONMENT_GET_SAVE_DIRECTORY: *(const char**)data = "/tmp"; return true;
  case RETRO_ENVIRONMENT_GET_CAN_DUPE: *(bool*)data = true; return true;
  case RETRO_ENVIRONMENT_GET_VARIABLE: {
    /* CORE_OPTS="key=value;key=value" lets us force accuracy settings */
    struct retro_variable *v = data; static char buf[4096]; const char *o = getenv("CORE_OPTS");
    if (getenv("ENVDBG")) fprintf(stderr, "var %s\n", v->key);
    v->value = NULL;
    if (o) {
      strncpy(buf, o, sizeof buf - 1);
      for (char *t = strtok(buf, ";"); t; t = strtok(NULL, ";")) {
        char *eq = strchr(t, '='); if (!eq) continue; *eq = 0;
        if (!strcmp(t, v->key)) { static char val[256]; strncpy(val, eq + 1, 255); v->value = val; return true; }
      }
    }
    return false; }
  case RETRO_ENVIRONMENT_GET_LOG_INTERFACE: ((struct retro_log_callback*)data)->log = log_cb; return true;
  default: return false;
  }
}
static void video_cb(const void *d, unsigned w, unsigned h, size_t pitch) {
  if (!d) return;
  lw = w; lh = h; lpitch = pitch;
  fbcopy = realloc(fbcopy, pitch * h);
  memcpy(fbcopy, d, pitch * h); lastfb = fbcopy;
}
/* set LR_AUDIO=out.raw to capture the core's audio (s16le stereo, core sample rate) */
static FILE *audf;
static void audio_cb(int16_t l, int16_t r) { if (audf) { int16_t s[2] = {l, r}; fwrite(s, 4, 1, audf); } }
static size_t audio_batch_cb(const int16_t *d, size_t f) { if (audf) fwrite(d, 4, f, audf); return f; }
static void input_poll_cb(void) {}
static int16_t input_state_cb(unsigned port, unsigned dev, unsigned idx, unsigned id) {
  if (port != 0 || dev != RETRO_DEVICE_JOYPAD) return 0;
  if (id == RETRO_DEVICE_ID_JOYPAD_MASK) return held;
  return (held >> id) & 1;
}
static void dump(const char *path) {
  if (!lastfb) return;
  FILE *f = fopen(path, "wb");
  fprintf(f, "P6\n%u %u\n255\n", lw, lh);
  for (unsigned y = 0; y < lh; y++) {
    const unsigned char *row = (const unsigned char*)lastfb + y * lpitch;
    for (unsigned x = 0; x < lw; x++) {
      unsigned char rgb[3];
      if (pixfmt == RETRO_PIXEL_FORMAT_XRGB8888) {
        unsigned v = ((const unsigned*)row)[x];
        rgb[0] = v >> 16; rgb[1] = v >> 8; rgb[2] = v;
      } else if (pixfmt == RETRO_PIXEL_FORMAT_RGB565) {
        unsigned v = ((const unsigned short*)row)[x];
        rgb[0] = ((v >> 11) & 31) * 255 / 31; rgb[1] = ((v >> 5) & 63) * 255 / 63; rgb[2] = (v & 31) * 255 / 31;
      } else {
        unsigned v = ((const unsigned short*)row)[x];
        rgb[0] = ((v >> 10) & 31) * 255 / 31; rgb[1] = ((v >> 5) & 31) * 255 / 31; rgb[2] = (v & 31) * 255 / 31;
      }
      fwrite(rgb, 1, 3, f);
    }
  }
  fclose(f);
}
static unsigned parse_buttons(const char *s) {
  static const struct { const char *n; int id; } map[] = {
    {"B",0},{"Y",1},{"SELECT",2},{"START",3},{"UP",4},{"DOWN",5},{"LEFT",6},{"RIGHT",7},
    {"A",8},{"X",9},{"L",10},{"R",11}};
  unsigned m = 0; char buf[256]; strncpy(buf, s, 255); buf[255]=0;
  for (char *t = strtok(buf, ","); t; t = strtok(NULL, ","))
    for (unsigned i = 0; i < sizeof map / sizeof *map; i++) if (!strcmp(t, map[i].n)) m |= 1u << map[i].id;
  return m;
}
#define SYM(n) n = dlsym(h, #n); if (!n) { fprintf(stderr, "missing %s\n", #n); return 1; }
int main(int argc, char **argv) {
  if (getenv("LR_AUDIO")) audf = fopen(getenv("LR_AUDIO"), "wb");
  if (argc < 5) { fprintf(stderr, "usage\n"); return 1; }
  void *h = dlopen(argv[1], RTLD_NOW); if (!h) { fprintf(stderr, "%s\n", dlerror()); return 1; }
  void (*retro_set_environment)(retro_environment_t); void (*retro_set_video_refresh)(retro_video_refresh_t);
  void (*retro_set_audio_sample)(retro_audio_sample_t); void (*retro_set_audio_sample_batch)(retro_audio_sample_batch_t);
  void (*retro_set_input_poll)(retro_input_poll_t); void (*retro_set_input_state)(retro_input_state_t);
  void (*retro_init)(void); bool (*retro_load_game)(const struct retro_game_info*); void (*retro_run)(void);
  void (*retro_set_controller_port_device)(unsigned, unsigned);
  SYM(retro_set_environment) SYM(retro_set_video_refresh) SYM(retro_set_audio_sample) SYM(retro_set_audio_sample_batch)
  SYM(retro_set_input_poll) SYM(retro_set_input_state) SYM(retro_init) SYM(retro_load_game) SYM(retro_run)
  SYM(retro_set_controller_port_device)
  retro_set_environment(env_cb); retro_init();
  retro_set_video_refresh(video_cb); retro_set_audio_sample(audio_cb); retro_set_audio_sample_batch(audio_batch_cb);
  retro_set_input_poll(input_poll_cb); retro_set_input_state(input_state_cb);
  FILE *rf = fopen(argv[2], "rb"); fseek(rf, 0, SEEK_END); long sz = ftell(rf); fseek(rf, 0, SEEK_SET);
  void *rom = malloc(sz); fread(rom, 1, sz, rf); fclose(rf);
  struct retro_game_info gi = { argv[2], rom, (size_t)sz, NULL };
  if (!retro_load_game(&gi)) { fprintf(stderr, "load failed\n"); return 1; }
  retro_set_controller_port_device(0, RETRO_DEVICE_JOYPAD);
  /* parse script */
  FILE *sf = fopen(argv[3], "r"); char line[512];
  struct ev { long fr; char cmd[16]; char a[256]; long n, step; } evs[4096]; int ne = 0;
  while (fgets(line, sizeof line, sf)) {
    if (line[0] == '#' || line[0] == '\n') continue;
    struct ev *e = &evs[ne]; e->a[0] = 0; e->n = 1; e->step = 1;
    if (sscanf(line, "%ld %15s %255s %ld %ld", &e->fr, e->cmd, e->a, &e->n, &e->step) >= 2) ne++;
  }
  fclose(sf);
  long rec_until = -1, rec_step = 1, rec_idx = 0, rec_start = 0; char rec_name[256] = "";
  for (long fr = 0;; fr++) {
    for (int i = 0; i < ne; i++) if (evs[i].fr == fr) {
      struct ev *e = &evs[i];
      if (!strcmp(e->cmd, "hold")) held = strcmp(e->a, "none") ? parse_buttons(e->a) : 0;
      else if (!strcmp(e->cmd, "rec")) { strcpy(rec_name, e->a); rec_start = fr; rec_until = fr + e->n * e->step; rec_step = e->step; rec_idx = 0; }
      else if (!strcmp(e->cmd, "pk")) {
        void *(*gm)(unsigned) = dlsym(h, "retro_get_memory_data"); unsigned char *rm = gm ? gm(RETRO_MEMORY_SYSTEM_RAM) : NULL;
        const char *pk = getenv("PEEK"); static char b3[1024];
        if (pk && rm) { strncpy(b3, pk, 1023); printf("pk %ld", fr); for (char *t = strtok(b3, ","); t; t = strtok(NULL, ",")) { unsigned a = strtoul(t, NULL, 16); printf(" %u", rm[a] | rm[a+1] << 8); } printf("\n"); fflush(stdout); }
      }
      else if (!strcmp(e->cmd, "end")) {
        const char *wd = getenv("WRAMDUMP");
        if (wd) {
          void *(*gmd2)(unsigned) = dlsym(h, "retro_get_memory_data");
          unsigned char *r2 = gmd2 ? gmd2(RETRO_MEMORY_SYSTEM_RAM) : NULL;
          FILE *wf = fopen(wd, "wb"); if (wf && r2) { fwrite(r2, 1, 131072, wf); fclose(wf); }
        }
        const char *pk = getenv("PEEK");
        if (pk) {
          void *(*gmd)(unsigned) = dlsym(h, "retro_get_memory_data");
          unsigned char *ram = gmd ? gmd(RETRO_MEMORY_SYSTEM_RAM) : NULL;
          static char b2[16384]; strncpy(b2, pk, 16383); b2[16383] = 0;
          for (char *t = strtok(b2, ","); t && ram; t = strtok(NULL, ",")) {
            unsigned a = strtoul(t, NULL, 16); printf("peek %04x = %u\n", a, ram[a] | ram[a+1] << 8);
          }
        }
        return 0;
      }
    }
    { /* BOT=st,x,z (hex WRAM addrs of en_st/en_x/en_z): from frame BOTFROM, steer at the nearest live enemy, fire */
      static int bi = -1; static unsigned bst, bx, bz, bfrom; static unsigned char *bram; static unsigned base;
      if (bi < 0) { bi = 0; const char *b = getenv("BOT"); if (b) { bi = 1; sscanf(b, "%x,%x,%x", &bst, &bx, &bz);
        bfrom = getenv("BOTFROM") ? atoi(getenv("BOTFROM")) : 0; void *(*g)(unsigned) = dlsym(h, "retro_get_memory_data"); bram = g(RETRO_MEMORY_SYSTEM_RAM); } }
      if (bi == 1 && fr == bfrom) base = held;
      if (bi == 1 && !bram) { void *(*g2)(unsigned) = dlsym(h, "retro_get_memory_data"); bram = g2(RETRO_MEMORY_SYSTEM_RAM); }
      if (bi == 1 && bram && fr >= bfrom) {
        int best = -1, bd = 1 << 30;
        for (int i = 0; i < 6; i++) {
          short st = bram[bst+2*i] | bram[bst+2*i+1] << 8; short x = bram[bx+2*i] | bram[bx+2*i+1] << 8; short z = bram[bz+2*i] | bram[bz+2*i+1] << 8;
          if (st != 1 || z < 0) continue;
          if (z < bd) { bd = z; best = x; }
        }
        { static int pi = -1; static unsigned pt, px, pz; if (pi < 0) { pi = 0; const char *q = getenv("BOTPU"); if (q) { pi = 1; sscanf(q, "%x,%x,%x", &pt, &px, &pz); } }
          if (pi == 1) for (int i = 0; i < 2; i++) {
            short t = bram[pt+2*i] | bram[pt+2*i+1] << 8; short x = bram[px+2*i] | bram[px+2*i+1] << 8; short z = bram[pz+2*i] | bram[pz+2*i+1] << 8;
            if (t > 0 && z > -100) { bd = z; best = x; break; }
          } }
        held = (base & ~((1u<<6)|(1u<<7))) | (1u<<1);
        if (bd != 1 << 30) { if (best < -40) held |= 1u<<6; else if (best > 40) held |= 1u<<7; if ((fr & 63) == 0) held |= 1u<<8; }
      }
    }
    retro_run();
    { static FILE *tf; static unsigned ta[64]; static int tn = -1; static unsigned char *tram;
      if (tn < 0) { tn = 0; const char *tr = getenv("TRACE"), *to = getenv("TRACEOUT");
        if (tr && to) { static char b3[4096]; strncpy(b3, tr, 4095);
          for (char *t = strtok(b3, ","); t && tn < 64; t = strtok(NULL, ",")) ta[tn++] = strtoul(t, NULL, 16);
          tf = fopen(to, "w"); void *(*g)(unsigned) = dlsym(h, "retro_get_memory_data"); tram = g(RETRO_MEMORY_SYSTEM_RAM); } }
      if (tf && tn) { fprintf(tf, "%ld", fr); for (int i = 0; i < tn; i++) fprintf(tf, " %u", tram[ta[i]] | tram[ta[i]+1] << 8); fputc('\n', tf); } }
    for (int i = 0; i < ne; i++) if (evs[i].fr == fr && !strcmp(evs[i].cmd, "shot")) {
      char p[1024]; snprintf(p, sizeof p, "%s/%s.ppm", argv[4], evs[i].a); dump(p);
    }
    if (fr < rec_until && (fr - rec_start) % rec_step == 0) {
      char p[1024]; snprintf(p, sizeof p, "%s/%s_%05ld.ppm", argv[4], rec_name, rec_idx++); dump(p);
    }
  }
}
