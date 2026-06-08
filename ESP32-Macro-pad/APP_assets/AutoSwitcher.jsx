/* ============================================================
   MACROPAD STUDIO — Auto-Switcher (context + AI)
   ============================================================ */
(function () {
  const { useState, useEffect } = React;
  const { Icon, Btn, IconBtn, Panel, Toggle, Field, Select } = window.UI;
  const M = window.MACRO;

  function MacroPreview({ actions }) {
    return (
      <div className="row wrap" style={{ gap: 5 }}>
        {actions.map((a, i) => (
          <React.Fragment key={i}>
            {i > 0 && <Icon name="caret-right" w="bold" style={{ fontSize: 11, color: "var(--text-faint)" }} />}
            <span className="chip mono">{M.summarize(a)}</span>
          </React.Fragment>
        ))}
      </div>
    );
  }

  function AutoSwitcher({ enabled, onToggle, activeCtx, setActiveCtx, regenKey }) {
    const [debug, setDebug] = useState(false);
    const ctx = M.CONTEXTS.find((c) => c.id === activeCtx) || M.CONTEXTS[0];

    return (
      <div className="view-enter">
        <div className="row between mb20" style={{ alignItems: "flex-end" }}>
          <div>
            <div className="page-title">Auto-Switcher</div>
            <div className="page-sub">The widget watches your focused app and suggests AI-generated macros for keys 1–4.</div>
          </div>
          <div className="row gap10">
            <span className="hint"><Icon name="bug" w="bold" /> Debug payloads</span>
            <Toggle on={debug} onChange={setDebug} />
            <div style={{ width: 1, height: 24, background: "var(--line)", margin: "0 4px" }} />
            <span className="hint">Auto-switch</span>
            <Toggle on={enabled} onChange={onToggle} />
          </div>
        </div>

        <div className="ctx-grid">
          <Panel title="Detected apps" icon="binoculars" sub="Window-title tracking" bodyClass="" >
            <div style={{ padding: 8 }}>
              {M.CONTEXTS.map((c) => (
                <button key={c.id} className={`ctx-item ${c.id === activeCtx ? "active" : ""}`} onClick={() => setActiveCtx(c.id)} style={{ width: "100%" }}>
                  <span className="ctx-ic"><Icon name={c.icon.replace("ph-", "")} w="bold" /></span>
                  <div className="col grow" style={{ alignItems: "flex-start" }}>
                    <span className="ctx-name">{c.label}</span>
                    <span className="ctx-sub">{c.sub}</span>
                  </div>
                  {c.id === activeCtx && <span className="conn-dot" style={{ background: "var(--accent)", boxShadow: "0 0 8px rgba(var(--accent-glow),0.8)" }} />}
                </button>
              ))}
            </div>
          </Panel>

          <Panel
            title={ctx.label}
            icon={ctx.icon.replace("ph-", "")}
            sub="AI-recommended bindings for this context"
            right={<Btn size="sm" icon="sparkle" onClick={() => regenKey(ctx.id, null)}>Regenerate all</Btn>}
          >
            {ctx.recs.map((r) => (
              <div className="rec-row" key={r.key_num}>
                <span className="rec-knum">K{r.key_num}</span>
                <div className="col grow" style={{ gap: 6 }}>
                  <span className="fw600 fs13">{r.description}</span>
                  <MacroPreview actions={r.actions} />
                </div>
                <IconBtn icon="arrow-clockwise" title="Regenerate this key" onClick={() => regenKey(ctx.id, r.key_num)} />
                <IconBtn icon="arrow-line-down" title="Push to device" />
              </div>
            ))}
            <div className="hint mt14"><Icon name="sparkle" w="fill" style={{ color: "var(--accent)" }} /> Generated locally · validated before binding. Provider configured in Settings.</div>
          </Panel>
        </div>
      </div>
    );
  }

  window.AutoSwitcher = AutoSwitcher;
})();
