/* ============================================================
   MACROPAD STUDIO — Settings (AI + advanced)
   ============================================================ */
(function () {
  const { useState } = React;
  const { Icon, Btn, Panel, Field, Select, Segmented, Toggle } = window.UI;

  const PROVIDERS = {
    "Ollama (Local)": { keyLabel: "Ollama URL", keyPlaceholder: "http://localhost:11434", secret: false, model: "llama3:70b", icon: "hard-drives" },
    "OpenAI":         { keyLabel: "API Key",    keyPlaceholder: "sk-…",                   secret: true,  model: "gpt-4o-mini", icon: "circle-half" },
    "Gemini":         { keyLabel: "API Key",    keyPlaceholder: "AIza…",                  secret: true,  model: "gemini-1.5-flash", icon: "sparkle" },
  };

  function Settings({ settings, onChange, advancedMode, onAdvancedMode, widgetAlpha, onWidgetAlpha }) {
    const prov = settings.provider;
    const meta = PROVIDERS[prov];
    const [showKey, setShowKey] = useState(false);

    return (
      <div className="view-enter">
        <div className="mb20">
          <div className="page-title">Settings</div>
          <div className="page-sub">Configure the AI engine, the floating widget, and power-user options.</div>
        </div>

        <div className="dash-grid">
          <div className="col" style={{ gap: 18 }}>
            <Panel title="AI engine" icon="brain" sub="Powers macro generation">
              <Field label="Provider">
                <Segmented value={prov} onChange={(v) => onChange({ ...settings, provider: v, model: PROVIDERS[v].model })}
                  options={Object.keys(PROVIDERS).map((p) => ({ value: p, label: p.split(" ")[0], icon: PROVIDERS[p].icon }))} />
              </Field>
              <div className="mt14"><Field label={meta.keyLabel}>
                <div className="row" style={{ gap: 8 }}>
                  <input className="input mono" type={meta.secret && !showKey ? "password" : "text"}
                    placeholder={meta.keyPlaceholder} value={settings.key}
                    onChange={(e) => onChange({ ...settings, key: e.target.value })} />
                  {meta.secret && <Btn size="sm" icon={showKey ? "eye-slash" : "eye"} onClick={() => setShowKey((v) => !v)} />}
                </div>
              </Field></div>
              <div className="mt14"><Field label="Model / tag">
                <input className="input mono" value={settings.model} onChange={(e) => onChange({ ...settings, model: e.target.value })} />
              </Field></div>
              <div className="row" style={{ gap: 8, marginTop: 16 }}>
                <Btn icon="plugs-connected" variant="primary">Test connection</Btn>
                <span className="hint"><Icon name="lock-simple" w="bold" /> Stored locally only</span>
              </div>
            </Panel>
          </div>

          <div className="col" style={{ gap: 18 }}>
            <Panel title="Floating widget" icon="app-window" sub="The always-on-top recommender">
              <div className="row between">
                <span className="fs13 fw600">Opacity</span>
                <span className="mono fs12 faint">{Math.round(widgetAlpha * 100)}%</span>
              </div>
              <input type="range" min="0.3" max="1" step="0.01" value={widgetAlpha}
                onChange={(e) => onWidgetAlpha(parseFloat(e.target.value))}
                style={{ width: "100%", marginTop: 10, accentColor: "var(--accent)" }} />
              <div className="divider" />
              <Row label="Stay on top" sub="Float above other windows" on={true} />
              <Row label="Snap to edges" sub="Magnetic window borders" on={true} />
              <Row label="Auto-hide when idle" sub="Fade out after 30s" on={false} />
            </Panel>

            <Panel title="Power user" icon="terminal" sub="Hidden depth, when you want it">
              <Row label="Advanced mode" sub="Reveal raw JSON & low-level fields everywhere" on={advancedMode} onChange={onAdvancedMode} />
              <Row label="Command palette" sub="Press ⌘K / Ctrl-K anywhere" on={true} />
              <Row label="Confirm destructive actions" sub="Ask before wiping a profile" on={true} />
              <div className="divider" />
              <div className="row" style={{ gap: 8 }}>
                <Btn size="sm" icon="export">Export all profiles</Btn>
                <Btn size="sm" variant="danger" icon="trash">Factory reset</Btn>
              </div>
            </Panel>
          </div>
        </div>
      </div>
    );
  }

  function Row({ label, sub, on, onChange }) {
    const [local, setLocal] = useState(on);
    const val = onChange ? on : local;
    return (
      <div className="row between" style={{ padding: "11px 0" }}>
        <div className="col">
          <span className="fs13 fw600">{label}</span>
          <span className="fs12 faint">{sub}</span>
        </div>
        <Toggle on={val} onChange={onChange || setLocal} />
      </div>
    );
  }

  window.Settings = Settings;
})();
