/* ============================================================
   MACROPAD STUDIO — Key Editor (device + builder)
   ============================================================ */
(function () {
  const { useState, useRef, useEffect } = React;
  const { Icon, IconBtn, rgbCss } = window.UI;
  const M = window.MACRO;

  function Keycap({ k, selected, pressing, onSelect }) {
    const meta = k && k.actions && k.actions[0] ? M.ACTION_META[k.actions[0].type] : null;
    const led = k ? M.ledColorOf(k) : null;
    const lit = !!led;
    return (
      <button
        className={`keycap ${selected ? "sel" : ""} ${lit ? "lit" : ""} ${pressing ? "pressing" : ""}`}
        onClick={onSelect}
      >
        {led && <span className="kc-led" style={{ background: `radial-gradient(circle at 50% 120%, ${rgbCss(led)}, transparent 75%)` }} />}
        <div className="row between" style={{ position: "relative" }}>
          <span className="kc-num">K{k.id}</span>
          {k.actions.length > 1 && <span className="kc-count">{k.actions.length}</span>}
        </div>
        <i className={`ph-bold ph-${meta ? meta.icon.replace("ph-", "") : "minus"} kc-icon`} style={{ position: "relative" }} />
        <span className="kc-name" style={{ position: "relative" }}>{k.name || "—"}</span>
      </button>
    );
  }

  function KeyEditor({ profile, selectedId, onSelect, pressingId, advanced, builderProps }) {
    const byId = {};
    profile.keys.forEach((k) => (byId[k.id] = k));
    const sel = byId[selectedId];

    const litCount = profile.keys.filter((k) => M.ledColorOf(k)).length;
    const totalActions = profile.keys.reduce((s, k) => s + k.actions.length, 0);

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
                      pressing={id === pressingId} onSelect={() => onSelect(id)} />
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
              <div className="meta-cell"><div className="l">Idle anim</div><div className="v" style={{ textTransform: "capitalize" }}>{profile.idle_animation}</div></div>
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
