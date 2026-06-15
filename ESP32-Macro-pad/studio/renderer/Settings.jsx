/* ============================================================
   MACROPAD STUDIO — Settings (AI + advanced)
   ============================================================ */
(function () {
  const { useState } = React;
  const { Icon, Btn, Panel, Field, Select, Segmented, Toggle, Confirm } = window.UI;

  const PROVIDERS = {
    "Ollama (Local)": { keyLabel: "Ollama URL", keyPlaceholder: "http://localhost:11434", secret: false, model: "llama3:70b", icon: "hard-drives" },
    "OpenAI":         { keyLabel: "API Key",    keyPlaceholder: "sk-…",                   secret: true,  model: "gpt-4o-mini", icon: "circle-half" },
    "Gemini":         { keyLabel: "API Key",    keyPlaceholder: "AIza…",                  secret: true,  model: "gemini-1.5-flash", icon: "sparkle" },
  };

  function Settings({ settings, onChange, advancedMode, onAdvancedMode, widgetAlpha, onWidgetAlpha, onTest,
                      theme = "dark", onToggleTheme, flags = {}, onFlag, onExportAll, onFactoryReset,
                      update = {}, onCheckUpdates, onInstallUpdate }) {
    const prov = settings.provider;
    const meta = PROVIDERS[prov];
    const [showKey, setShowKey] = useState(false);
    const [testState, setTestState] = useState(null); // null | "testing" | "ok" | "fail"
    const [showReset, setShowReset] = useState(false);
    const flag = (k, dflt = false) => (flags[k] != null ? flags[k] : dflt);
    const updateLabel = ({
      checking: "Checking for updates…",
      downloading: `Downloading update… ${update.percent != null ? update.percent + "%" : ""}`,
      downloaded: `Version ${update.version || ""} ready to install`,
      none: "You're up to date",
      error: "Update check failed",
    })[update.status] || "";
    const requestReset = () => { if (flag("confirm_destructive", true)) setShowReset(true); else onFactoryReset && onFactoryReset(); };
    const runTest = () => {
      if (!onTest) return;
      setTestState("testing");
      onTest().then((r) => setTestState(r && r.ok ? "ok" : "fail")).catch(() => setTestState("fail"));
    };

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
                <Btn icon="plugs-connected" variant="primary" onClick={runTest} disabled={testState === "testing"}>
                  {testState === "testing" ? "Testing…" : "Test connection"}
                </Btn>
                {testState === "ok" && <span className="hint" style={{ color: "var(--ok, #2fe6a8)" }}><Icon name="check-circle" w="bold" /> Connected</span>}
                {testState === "fail" && <span className="hint" style={{ color: "var(--danger, #ff5d6c)" }}><Icon name="warning" w="bold" /> Failed</span>}
                {!testState && <span className="hint"><Icon name="lock-simple" w="bold" /> Stored locally only</span>}
              </div>
            </Panel>

            <Panel title="Appearance" icon="palette" sub="Studio theme">
              <Field label="Theme">
                <Segmented value={theme}
                  onChange={(v) => { if (v !== theme && onToggleTheme) onToggleTheme(); }}
                  options={[{ value: "dark", label: "Dark", icon: "moon-stars" }, { value: "light", label: "Light", icon: "sun" }]} />
              </Field>
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
              <Row label="Stay on top" sub="Float above other windows" on={flag("widget_stay_on_top", true)} onChange={(v) => onFlag("widget_stay_on_top", v)} />
              <Row label="Snap to edges" sub="Magnetic screen-edge borders" on={flag("widget_snap", true)} onChange={(v) => onFlag("widget_snap", v)} />
              <Row label="Auto-hide when idle" sub="Hide after 8s without a keypress" on={flag("widget_auto_hide")} onChange={(v) => onFlag("widget_auto_hide", v)} />
            </Panel>

            <Panel title="Power user" icon="terminal" sub="Hidden depth, when you want it">
              <Row label="Advanced mode" sub="Reveal raw JSON & low-level fields everywhere" on={advancedMode} onChange={onAdvancedMode} />
              <Row label="Launch at startup" sub="Open Macropad Studio when you log in" on={flag("open_at_login")} onChange={(v) => onFlag("open_at_login", v)} />
              <Row label="Confirm destructive actions" sub="Ask before resetting or wiping" on={flag("confirm_destructive", true)} onChange={(v) => onFlag("confirm_destructive", v)} />
              <div className="divider" />
              <div className="row" style={{ gap: 8 }}>
                <Btn size="sm" icon="export" onClick={onExportAll}>Export all profiles</Btn>
                <Btn size="sm" variant="danger" icon="trash" onClick={requestReset}>Factory reset</Btn>
              </div>
            </Panel>

            <Panel title="About" icon="info" sub="Macropad Studio">
              <div className="row between">
                <span className="fs13 fw600">Macropad Studio</span>
                <span className="mono fs12 faint">v2.0.1</span>
              </div>
              <span className="fs12 faint">Configurator for the ESP32-S2 macropad — device sync + local-AI macro generation.</span>
              <div className="divider" />
              <span className="fs12 faint">Developed by</span>
              <div className="fs13 fw600" style={{ marginTop: 2 }}>Aditya Biswas</div>
              <div className="row" style={{ gap: 8, marginTop: 12 }}>
                <Link href="https://github.com/adi04jan" icon="github-logo">GitHub</Link>
                <Link href="https://www.linkedin.com/in/aditya-biswas-6409b78b/" icon="linkedin-logo">LinkedIn</Link>
              </div>
              <div className="divider" />
              <div className="row between">
                <span className="fs12 faint">{updateLabel || "Updates"}</span>
                {update.status === "downloaded"
                  ? <Btn size="sm" variant="primary" icon="arrow-circle-up" onClick={onInstallUpdate}>Restart to update</Btn>
                  : <Btn size="sm" icon="arrows-clockwise" onClick={onCheckUpdates}
                      disabled={update.status === "checking" || update.status === "downloading"}>Check for updates</Btn>}
              </div>
            </Panel>
          </div>
        </div>

        <Confirm open={showReset} title="Factory reset?"
          message="This restores all settings to defaults and clears your saved templates and usage stats. Profiles stored on the device are not touched. This cannot be undone."
          confirmLabel="Reset everything"
          onCancel={() => setShowReset(false)}
          onConfirm={() => { setShowReset(false); onFactoryReset && onFactoryReset(); }} />
      </div>
    );
  }

  function Link({ href, icon, children }) {
    return (
      <a href={href} target="_blank" rel="noreferrer"
        style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "8px 13px",
          borderRadius: 10, background: "var(--surface-2, #16161f)", color: "var(--text, #e8e8ef)",
          textDecoration: "none", fontSize: 13, fontWeight: 600, border: "1px solid var(--border, #262634)" }}>
        <Icon name={icon} w="bold" /> {children}
      </a>
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
