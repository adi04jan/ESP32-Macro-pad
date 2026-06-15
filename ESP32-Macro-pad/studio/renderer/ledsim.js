/* ============================================================
   MACROPAD STUDIO — LED simulator
   A faithful JS port of the firmware LED engine (leds.cpp) so the on-screen
   keypad mirrors the device's animation in real time. Same patterns, same
   physical key positions, same easing/press/ripple math. Driven by a rAF loop
   in the Key Editor; fed key + idle events from the device.
   ============================================================ */
(function () {
  const N = 12;

  // Physical (col,row) per HARDWARE index (LED/button chain) — mirrors firmware
  // KEY_POS_INIT. The sim runs entirely in hardware-index space, exactly like the
  // device, and only remaps logical<->hardware at the edges (set/keyDown/colorAt).
  const POS = [[2,0],[1,0],[0,1],[1,1],[2,1],[3,1],[3,2],[2,2],[1,2],[0,2],[1,3],[2,3]];
  // Natural key number (1..12, 0-based) -> hardware index (mirrors firmware LOGICAL_TO_HW_INIT).
  const LOGICAL_TO_HW = [1, 0, 2, 3, 4, 5, 9, 8, 7, 6, 10, 11];
  const hwOf = (logicalIdx) => (logicalIdx >= 0 && logicalIdx < N ? LOGICAL_TO_HW[logicalIdx] : -1);

  // Tuning constants (mirror config.h).
  const EASE = 0.22, PRESS_RISE = 1.0, PRESS_FADE = 0.12;
  const BREATHE_SPEED = 0.05, BREATHE_FLOOR = 0.12, RAINBOW_SPEED = 2;
  const WAVE_SPEED = 2.2, WAVE_HUE_STEP = 30.0;
  const COMET_SPEED = 0.16, COMET_TAIL = 4.0, COMET_HUE_SPEED = 1, COMET_FLOOR = 0.04;
  const TWK_CHANCE = 7, TWK_RISE = 0.16, TWK_FADE = 0.05, TWK_BOOST = 1.0;
  const RIP_MAX = 4, RIP_SPEED = 0.085, RIP_WIDTH = 0.9, RIP_LIFE = 4.6;

  const clampf = (v) => (v < 0 ? 0 : v > 255 ? 255 : v);
  const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

  // hue 0..255 -> rgb (same wheel as the firmware).
  function wheel(h) {
    h = ((h % 256) + 256) % 256;
    let r, g, b;
    if (h < 85) { r = h * 3; g = 0; b = 255 - h * 3; }
    else if (h < 170) { h -= 85; r = 255 - h * 3; g = h * 3; b = 0; }
    else { h -= 170; r = 0; g = 255 - h * 3; b = h * 3; }
    return [r, g, b];
  }

  class LedSim {
    constructor() {
      this.base = Array.from({ length: N }, () => [0, 0, 0]);
      this.cur = Array.from({ length: N }, () => [0, 0, 0]);
      this.out = Array.from({ length: N }, () => [0, 0, 0]);
      this.press = new Array(N).fill(0);
      this.held = new Array(N).fill(false);
      this.twk = new Array(N).fill(0);
      this.twRising = new Array(N).fill(false);
      this.ripples = Array.from({ length: RIP_MAX }, () => ({ cx: 0, cy: 0, age: 0, active: false }));
      this.mode = "none";
      this.breathe = 0; this.rainbow = 0; this.wave = 0; this.cometHead = 0; this.cometHue = 0;
      this.ext = null; this.extAt = 0;   // streamed device frame (exact, in-sync) + timestamp
    }

    // The device's actual framebuffer (hardware order). When fresh, it overrides
    // the local simulation so the on-screen mirror is exactly in sync.
    setFrame(hwArray) { if (Array.isArray(hwArray) && hwArray.length >= N) { this.ext = hwArray; this.extAt = (typeof performance !== "undefined" ? performance.now() : Date.now()); } }

    setMode(name) {
      this.mode = name || "none";
      if (this.mode !== "twinkle") this.twk.fill(0);
      if (this.mode !== "ripple") this.ripples.forEach((r) => (r.active = false));
    }
    // Inputs use the natural (logical) key index; we store at the hardware index.
    setBase(logicalIdx, rgb) {
      const h = hwOf(logicalIdx); if (h < 0) return;
      this.base[h] = (Array.isArray(rgb) && rgb.length >= 3) ? [rgb[0], rgb[1], rgb[2]] : [0, 0, 0];
    }
    setBaseFromKeys(keys) {
      for (let i = 0; i < N; i++) this.base[i] = [0, 0, 0];
      (keys || []).forEach((k) => {
        const h = hwOf((k && k.id || 0) - 1); if (h < 0) return;
        const g = k.glow;
        this.base[h] = (Array.isArray(g) && g.length >= 3) ? [g[0], g[1], g[2]] : [0, 0, 0];
      });
    }
    keyDown(logicalIdx) { const h = hwOf(logicalIdx); if (h < 0) return; this.held[h] = true; this.press[h] = PRESS_RISE; if (this.mode === "ripple") this._spawn(h); }
    keyUp(logicalIdx) { const h = hwOf(logicalIdx); if (h >= 0) this.held[h] = false; }

    _spawn(i) {
      let slot = -1, oldest = -1;
      for (let r = 0; r < RIP_MAX; r++) {
        if (!this.ripples[r].active) { slot = r; break; }
        if (this.ripples[r].age > oldest) { oldest = this.ripples[r].age; slot = r; }
      }
      const rp = this.ripples[slot];
      rp.cx = POS[i][0]; rp.cy = POS[i][1]; rp.age = 0; rp.active = true;
    }

    tick() {
      this.breathe += BREATHE_SPEED; if (this.breathe > Math.PI * 2) this.breathe -= Math.PI * 2;
      this.rainbow = (this.rainbow + RAINBOW_SPEED) & 0xFF;
      this.wave += WAVE_SPEED; if (this.wave > 256) this.wave -= 256;
      this.cometHead += COMET_SPEED; if (this.cometHead >= N) this.cometHead -= N;
      this.cometHue = (this.cometHue + COMET_HUE_SPEED) & 0xFF;
      const breatheEnv = BREATHE_FLOOR + (1 - BREATHE_FLOOR) * 0.5 * (1 + Math.sin(this.breathe));

      if (this.mode === "ripple") {
        for (const r of this.ripples) { if (!r.active) continue; r.age += RIP_SPEED; if (r.age > RIP_LIFE) r.active = false; }
      }

      for (let i = 0; i < N; i++) {
        let tr, tg, tb;
        if (this.mode === "rainbow") {
          [tr, tg, tb] = wheel(Math.floor(i * 256 / N) + this.rainbow);
        } else if (this.mode === "wave") {
          [tr, tg, tb] = wheel(Math.floor((POS[i][0] + POS[i][1]) * WAVE_HUE_STEP - this.wave));
        } else if (this.mode === "comet") {
          let dist = this.cometHead - i; if (dist < 0) dist += N;
          let br = 1 - dist / COMET_TAIL; if (br < COMET_FLOOR) br = COMET_FLOOR;
          const c = wheel(this.cometHue - Math.floor(dist * 12));
          tr = c[0] * br; tg = c[1] * br; tb = c[2] * br;
        } else {
          tr = this.base[i][0]; tg = this.base[i][1]; tb = this.base[i][2];
          if (this.mode === "breathe") { tr *= breatheEnv; tg *= breatheEnv; tb *= breatheEnv; }
        }

        const c = this.cur[i];
        c[0] += (tr - c[0]) * EASE; c[1] += (tg - c[1]) * EASE; c[2] += (tb - c[2]) * EASE;
        let orr = c[0], org = c[1], orb = c[2];

        // twinkle bloom
        if (this.mode === "twinkle") {
          if (this.twk[i] <= 0.001) { if (Math.random() * 1000 < TWK_CHANCE) { this.twk[i] = 0.02; this.twRising[i] = true; } else this.twk[i] = 0; }
          else if (this.twRising[i]) { this.twk[i] += TWK_RISE; if (this.twk[i] >= 1) { this.twk[i] = 1; this.twRising[i] = false; } }
          else { this.twk[i] -= TWK_FADE; if (this.twk[i] < 0) this.twk[i] = 0; }
          const t = this.twk[i] * TWK_BOOST;
          if (t > 0) { orr = orr * (1 - t) + 255 * t; org = org * (1 - t) + 255 * t; orb = orb * (1 - t) + 255 * t; }
        } else if (this.twk[i] !== 0) { this.twk[i] = 0; }

        // press highlight
        if (this.held[i]) this.press[i] = PRESS_RISE;
        else if (this.press[i] > 0.002) this.press[i] *= (1 - PRESS_FADE);
        else this.press[i] = 0;
        const p = this.press[i];
        if (p > 0) { orr = orr * (1 - p) + 255 * p; org = org * (1 - p) + 255 * p; orb = orb * (1 - p) + 255 * p; }

        // ripple rings
        if (this.mode === "ripple") {
          let add = 0;
          for (const r of this.ripples) {
            if (!r.active) continue;
            const dx = POS[i][0] - r.cx, dy = POS[i][1] - r.cy;
            const d = Math.sqrt(dx * dx + dy * dy);
            const inten = 1 - Math.abs(d - r.age) / RIP_WIDTH;
            if (inten <= 0) continue;
            const life = 1 - r.age / RIP_LIFE;
            const v = inten * (life < 0 ? 0 : life);
            if (v > add) add = v;
          }
          add = clamp01(add);
          if (add > 0) { orr = orr * (1 - add) + 255 * add; org = org * (1 - add) + 255 * add; orb = orb * (1 - add) + 255 * add; }
        }

        this.out[i][0] = clampf(orr); this.out[i][1] = clampf(org); this.out[i][2] = clampf(orb);
      }
      return this.out;
    }

    // Natural key index in -> the hardware LED's colour out. Prefer the live
    // streamed device frame when it's fresh; fall back to the local simulation.
    colorAt(logicalIdx) {
      const h = hwOf(logicalIdx); if (h < 0) return [0, 0, 0];
      const now = (typeof performance !== "undefined" ? performance.now() : Date.now());
      if (this.ext && now - this.extAt < 400) return this.ext[h] || [0, 0, 0];
      return this.out[h] || [0, 0, 0];
    }
  }

  window.LedSim = LedSim;
})();
