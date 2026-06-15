/* ============================================================
   MACROPAD STUDIO — Key Editor (device + builder)
   ============================================================ */
(function () {
  const { useState, useRef, useEffect } = React;
  const { Icon, IconBtn, rgbCss } = window.UI;
  const M = window.MACRO;

  const h2 = (n) => Math.max(0, Math.min(255, n | 0)).toString(16).padStart(2, "0");
  const rgbToHex = (rgb) => (Array.isArray(rgb) && rgb.length >= 3) ? `#${h2(rgb[0])}${h2(rgb[1])}${h2(rgb[2])}` : "#000000";
  const hexToRgb = (hex) => { const n = parseInt((hex || "").slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };

  function Keycap({ k, selected, pressing, onSelect, ledRef }) {
    const meta = k && k.actions && k.actions[0] ? M.ACTION_META[k.actions[0].type] : null;
    const lit = !!(k && M.ledColorOf(k));
    return (
      <button
        className={`keycap ${selected ? "sel" : ""} ${lit ? "lit" : ""} ${pressing ? "pressing" : ""}`}
        onClick={onSelect}
      >
        {/* live LED glow — colour/opacity driven each frame by the simulator */}
        <span className="kc-led" ref={ledRef} style={{ opacity: 0 }} />
        <div className="row between" style={{ position: "relative" }}>
          <span className="kc-num">K{k.id}</span>
          {k.actions.length > 1 && <span className="kc-count">{k.actions.length}</span>}
        </div>
        <i className={`ph-bold ph-${meta ? meta.icon.replace("ph-", "") : "minus"} kc-icon`} style={{ position: "relative" }} />
        <span className="kc-name" style={{ position: "relative" }}>{k.name || "—"}</span>
      </button>
    );
  }

  function KeyEditor({ profile, selectedId, onSelect, onSetGlow, sim, liveIdle, pressingId, advanced, builderProps }) {
    const byId = {};
    profile.keys.forEach((k) => (byId[k.id] = k));
    const sel = byId[selectedId];

    const litCount = profile.keys.filter((k) => M.ledColorOf(k)).length;
    const totalActions = profile.keys.reduce((s, k) => s + k.actions.length, 0);

    // Live LED mirror: paint every key from the simulator each animation frame.
    const ledRefs = useRef({});
    useEffect(() => {
      if (!sim) return;
      let raf;
      const paint = () => {
        sim.tick();
        const refs = ledRefs.current;
        for (const id in refs) {
          const el = refs[id];
          if (!el) continue;
          const c = sim.colorAt((id | 0) - 1);
          const r = c[0] | 0, g = c[1] | 0, b = c[2] | 0;
          const bright = Math.max(r, g, b) / 255;
          el.style.background = `radial-gradient(circle at 50% 120%, rgb(${r},${g},${b}) 0%, transparent 72%)`;
          el.style.opacity = bright <= 0.015 ? 0 : Math.min(1, bright * 1.15);
        }
        raf = requestAnimationFrame(paint);
      };
      raf = requestAnimationFrame(paint);
      return () => cancelAnimationFrame(raf);
    }, [sim]);

    return (
      <div className="view-enter">
        <div className="row between mb20" style={{ alignItems: "flex-end" }}>
          <div>
            <div className="page-title">Key Editor</div>
            <div className="page-sub">Click a key on your macropad, then build its action sequence.</div>
          </div>
          <span className="chip accent"><Icon name="cpu" w="bold" /> {profile.profile_name}</span>
        </div>

        <div className="editor-grid">
          {/* DEVICE */}
          <div className="device-wrap">
            <div className="device">
              <div className="device-top">
                <div className="device-brand"><Icon name="circles-three-plus" w="fill" style={{ color: "var(--accent)" }} /> MACROPAD · 12</div>
                <div className="device-knob" title="Rotary encoder" />
              </div>
              <div className="keygrid">
                {M.LAYOUT.flat().map((id, i) =>
                  id == null ? (
                    <div className="keycap-empty" key={"e" + i} />
                  ) : (
                    <Keycap key={id} k={byId[id]} selected={id === selectedId}
                      pressing={id === pressingId} onSelect={() => onSelect(id)}
                      ledRef={(el) => { if (el) ledRefs.current[id] = el; }} />
                  )
                )}
              </div>
              <div className="device-foot">
                <span className="mono">USB-HID · 115200</span>
                <span className="device-leds"><i /><i /><i /></span>
              </div>
            </div>

            <div className="device-meta">
              <div className="meta-cell"><div className="l">Keys mapped</div><div className="v">{profile.keys.filter(k=>k.actions.length).length} / 12</div></div>
              <div className="meta-cell"><div className="l">Total steps</div><div className="v">{totalActions}</div></div>
              <div className="meta-cell"><div className="l">Lit keys</div><div className="v">{litCount}</div></div>
              <div className="meta-cell"><div className="l">Idle anim</div><div className="v" style={{ textTransform: "capitalize" }}>{liveIdle || profile.idle_animation}</div></div>
            </div>

            {/* per-key resting LED colour */}
            <div className="panel" style={{ padding: "14px 16px", marginTop: 14 }}>
              <div className="row between" style={{ alignItems: "center" }}>
                <div>
                  <div className="section-label">Key {selectedId} LED colour</div>
                  <div className="mono fs12 faint">{sel && sel.glow ? `rgb(${sel.glow.join(", ")})` : "off (unlit)"}</div>
                </div>
                <div className="row" style={{ gap: 10, alignItems: "center" }}>
                  <input type="color" value={rgbToHex(sel && sel.glow)} title="Pick resting colour"
                    onChange={(e) => onSetGlow(selectedId, hexToRgb(e.target.value))}
                    style={{ width: 44, height: 34, padding: 0, border: "1px solid var(--line)", borderRadius: 8, background: "transparent", cursor: "pointer" }} />
                  <button className="btn sm" onClick={() => onSetGlow(selectedId, null)}>Off</button>
                </div>
              </div>
              <div className="mono fs12 faint" style={{ marginTop: 8 }}>Live on the device when connected · saved on upload.</div>
            </div>
          </div>

          {/* BUILDER */}
          <div className="panel" style={{ padding: 24, minHeight: 480 }}>
            {sel && window.ActionBuilder &&
              React.createElement(window.ActionBuilder, { keyData: sel, defaultAdvanced: advanced, ...builderProps })}
          </div>
        </div>
      </div>
    );
  }

  window.KeyEditor = KeyEditor;
})();
