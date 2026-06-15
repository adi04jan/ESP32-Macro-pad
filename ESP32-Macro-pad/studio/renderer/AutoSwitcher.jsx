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

  function AutoSwitcher({ enabled, onToggle, activeCtx, setActiveCtx, regenKey, recsFor, onPush, busy, detectedApp, autoAssign, onToggleAutoAssign }) {
    const ctx = M.CONTEXTS.find((c) => c.id === activeCtx) || M.CONTEXTS[0];
    const recs = (recsFor ? recsFor(ctx.id) : []) || [];

    return (
      <div className="view-enter">
        <div className="row between mb20" style={{ alignItems: "flex-end" }}>
          <div>
            <div className="page-title">Auto-Switcher</div>
            <div className="page-sub">Detects your focused app and ranks shortcuts by use — the keys you press most rise to the top.</div>
          </div>
          <div className="row gap10">
            <span className="hint"><Icon name="binoculars" w="bold" /> {enabled ? (detectedApp ? "Focused: " + detectedApp : "Watching…") : "Detection off"}</span>
            <div style={{ width: 1, height: 24, background: "var(--line)", margin: "0 4px" }} />
            <span className="hint">Auto-switch</span>
            <Toggle on={enabled} onChange={onToggle} />
            <div style={{ width: 1, height: 24, background: "var(--line)", margin: "0 4px" }} />
            <span className="hint" title="Override the macropad keys with this app's top shortcuts (live, not saved)">Auto-assign keys</span>
            <Toggle on={autoAssign} onChange={onToggleAutoAssign} />
          </div>
        </div>

        <div className="ctx-grid">
          <Panel title="App contexts" icon="binoculars" sub={enabled ? "auto-detected" : "manual"} bodyClass="" >
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
            right={<Btn size="sm" icon="sparkle" disabled={busy} onClick={() => regenKey(ctx.id, "all")}>{busy ? "Generating…" : "Regenerate all"}</Btn>}
          >
            {recs.length === 0 && <div className="hint"><Icon name="sparkle" w="bold" /> No shortcuts yet for this app.</div>}
            {recs.map((r, i) => (
              <div className="rec-row" key={i}>
                <span className="rec-knum">{i + 1}</span>
                <div className="col grow" style={{ gap: 6 }}>
                  <div className="row" style={{ gap: 8, alignItems: "center" }}>
                    <span className="fw600 fs13">{r.description}</span>
                    {r.uses ? <span className="chip accent" style={{ fontSize: 10 }}><Icon name="trend-up" w="bold" /> {r.uses}</span> : null}
                  </div>
                  <MacroPreview actions={r.actions} />
                </div>
                <IconBtn icon="arrow-line-down" title={`Push to K${r.key_num}`} onClick={() => onPush && onPush(r)} />
              </div>
            ))}
            <div className="hint mt14"><Icon name="trend-up" w="fill" style={{ color: "var(--accent)" }} /> Ranked by your usage · refreshed automatically. AI provider configured in Settings.</div>
          </Panel>
        </div>
      </div>
    );
  }

  window.AutoSwitcher = AutoSwitcher;
})();
