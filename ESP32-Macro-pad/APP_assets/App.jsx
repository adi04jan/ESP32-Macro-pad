/* ============================================================
   MACROPAD STUDIO — App shell + state
   ============================================================ */
(function () {
  const { useState, useEffect, useRef, useCallback } = React;
  const { Icon, IconBtn, Btn } = window.UI;
  const M = window.MACRO;

  const NAV = [
    { id: "editor", label: "Editor", icon: "sliders" },
    { id: "dashboard", label: "Device", icon: "gauge" },
    { id: "auto", label: "AI", icon: "sparkle" },
    { id: "settings", label: "Settings", icon: "gear-six" },
  ];
  const VIEW_LABEL = { editor: "Key Editor", dashboard: "Dashboard", auto: "Auto-Switcher", settings: "Settings" };

  const clone = (o) => JSON.parse(JSON.stringify(o));
  const now = () => { const d = new Date(); return d.toTimeString().slice(0, 8); };

  function App() {
    const [theme, setTheme] = useState(() => localStorage.getItem("mp_theme") || "dark");
    const [view, setView] = useState("editor");
    const [profile, setProfile] = useState(() => clone(M.SEED));
    const [selectedId, setSelectedId] = useState(1);
    const [pressingId, setPressingId] = useState(null);
    const [runningIndex, setRunningIndex] = useState(null);

    const [connected, setConnected] = useState(false);
    const [port, setPort] = useState(M.PORTS[1]);
    const [logs, setLogs] = useState([]);
    const [storage, setStorage] = useState({ total: 0, used: 0 });

    const [autoEnabled, setAutoEnabled] = useState(true);
    const [activeCtx, setActiveCtx] = useState("vscode");
    const [widgetOpen, setWidgetOpen] = useState(true);

    const [cmdkOpen, setCmdkOpen] = useState(false);
    const [advanced, setAdvanced] = useState(false);
    const [settings, setSettings] = useState({ provider: "Ollama (Local)", key: "http://localhost:11434", model: "llama3:70b" });
    const [widgetAlpha, setWidgetAlpha] = useState(0.98);

    useEffect(() => { document.documentElement.setAttribute("data-theme", theme); localStorage.setItem("mp_theme", theme); }, [theme]);

    // ⌘K
    useEffect(() => {
      const onKey = (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmdkOpen((v) => !v); }
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, []);

    const log = useCallback((text, opts = {}) => {
      setLogs((l) => [...l.slice(-80), { t: now(), text, ...opts }]);
    }, []);

    // ---- profile mutations ----
    const mutateKey = (id, fn) => setProfile((p) => {
      const np = clone(p);
      const k = np.keys.find((x) => x.id === id);
      fn(k);
      return np;
    });
    const updateGlobal = (key, val) => setProfile((p) => ({ ...p, [key]: val }));
    const renameKey = (name) => mutateKey(selectedId, (k) => (k.name = name));
    const changeAction = (i, na) => mutateKey(selectedId, (k) => (k.actions[i] = na));
    const deleteAction = (i) => mutateKey(selectedId, (k) => k.actions.splice(i, 1));
    const addAction = (a) => mutateKey(selectedId, (k) => k.actions.push(a));
    const reorder = (from, to) => mutateKey(selectedId, (k) => {
      const [m] = k.actions.splice(from, 1); k.actions.splice(to, 0, m);
    });

    // ---- test animation ----
    const testRef = useRef(false);
    const testKey = useCallback(() => {
      if (testRef.current) return;
      const key = profile.keys.find((k) => k.id === selectedId);
      if (!key || !key.actions.length) return;
      testRef.current = true;
      setPressingId(selectedId);
      if (connected) log(`Testing key ${selectedId} (${key.name})`, { prompt: true, cls: "ac" });
      let i = 0;
      const step = () => {
        if (i >= key.actions.length) {
          setRunningIndex(null); setPressingId(null); testRef.current = false;
          if (connected) log("Macro complete ✓", { cls: "ok" });
          return;
        }
        setRunningIndex(i);
        const a = key.actions[i];
        const dur = a.type === "delay" ? Math.max(180, Math.min(900, a.ms || 100)) : 420;
        i++;
        setTimeout(step, dur);
      };
      step();
    }, [profile, selectedId, connected, log]);

    // ---- connection sim ----
    const toggleConn = useCallback(() => {
      if (connected) {
        setConnected(false);
        log("Disconnected from serial port.", { cls: "er" });
        return;
      }
      setConnected(true);
      log(`Opening ${port}…`);
      setTimeout(() => log("Connected at 115200 baud.", { cls: "ok" }), 350);
      setTimeout(() => log("fsinfo", { prompt: true }), 800);
      setTimeout(() => {
        const used = 380 + profile.keys.reduce((s, k) => s + k.actions.length, 0) * 14;
        setStorage({ total: 1536 * 1024, used: used * 1024 / 4 });
        log(`FS_INFO: 1536KB total · ${(used / 4).toFixed(0)}KB used`, { cls: "ac" });
        log("Ready.", { cls: "ok" });
      }, 1150);
    }, [connected, port, profile, log]);

    const syncProfile = (mode) => {
      if (mode === "save") {
        log(`Uploading ${profile.profile_name}…`, { prompt: true });
        setTimeout(() => log("###BEGIN### profile" + profile.active + ".json", {}), 250);
        setTimeout(() => log("Upload sequence sent.", { cls: "ok" }), 700);
        setTimeout(() => log(`Setting active profile to ${profile.active}`, { cls: "ac" }), 950);
      } else {
        log(`Fetching profile${profile.active}.json from device…`, { prompt: true });
        setTimeout(() => log("Profile loaded and mapped to GUI.", { cls: "ok" }), 700);
      }
    };

    const setActive = (n) => { updateGlobal("active", n); if (connected) log(`setprofile ${n}`, { prompt: true, cls: "ac" }); };

    const regenKey = (ctxId, kn) => {
      log(`AI: regenerating ${kn ? "key " + kn : "all keys"} for [${ctxId}]…`, { cls: "ac" });
    };

    // ---- command palette runner ----
    const runCmd = (kind, arg) => {
      if (kind === "nav") setView(arg);
      else if (kind === "theme") setTheme((t) => (t === "dark" ? "light" : "dark"));
      else if (kind === "widget") setWidgetOpen((v) => !v);
      else if (kind === "advanced") setAdvanced((v) => !v);
      else if (kind === "connect") toggleConn();
      else if (kind === "test") { setView("editor"); testKey(); }
      else if (kind === "key") { setView("editor"); setSelectedId(arg); }
    };

    const builderProps = { onRename: renameKey, onChangeAction: changeAction, onDeleteAction: deleteAction,
      onAddAction: addAction, onReorder: reorder, onTest: testKey, runningIndex };

    return (
      <div className="app">
        {/* RAIL */}
        <nav className="rail">
          <div className="rail-logo"><Icon name="circles-three-plus" w="fill" /></div>
          {NAV.map((n) => (
            <button key={n.id} className={`rail-item ${view === n.id ? "active" : ""}`} onClick={() => setView(n.id)}>
              <Icon name={n.icon} w={view === n.id ? "fill" : "bold"} /><span>{n.label}</span>
            </button>
          ))}
          <div className="rail-spacer" />
          <button className="rail-item" onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))} title="Toggle theme">
            <Icon name={theme === "dark" ? "sun" : "moon-stars"} w="bold" /><span>{theme === "dark" ? "Light" : "Dark"}</span>
          </button>
        </nav>

        {/* MAIN */}
        <div className="main">
          <header className="topbar">
            <div className="tb-title">
              <b>{VIEW_LABEL[view]}</b>
              <span>macropad-studio · v4</span>
            </div>
            <div className="tb-spacer" />
            <button className={`conn-pill ${connected ? "on" : ""}`} onClick={() => setView("dashboard")}>
              <span className="conn-dot" /> {connected ? port.split(" ")[0] + " · live" : "Offline"}
            </button>
            <div style={{ width: 1, height: 26, background: "var(--line)" }} />
            <button className="btn sm" onClick={() => setCmdkOpen(true)}>
              <Icon name="magnifying-glass" w="bold" /> <span className="kbd" style={{ marginLeft: 2 }}>⌘K</span>
            </button>
            <IconBtn icon="code" w="bold" title="Advanced mode" className={advanced ? "" : ""}
              onClick={() => setAdvanced((v) => !v)} style={advanced ? { color: "var(--accent)", background: "var(--hover)" } : null} />
            <IconBtn icon={widgetOpen ? "app-window" : "app-window"} w="bold" title="Toggle AI widget"
              onClick={() => setWidgetOpen((v) => !v)} style={widgetOpen ? { color: "var(--accent)" } : null} />
          </header>

          <div className="view-scroll" key={view}>
            <div className="view-pad">
              {view === "editor" && React.createElement(window.KeyEditor, {
                profile, selectedId, onSelect: setSelectedId, pressingId, advanced, builderProps,
              })}
              {view === "dashboard" && React.createElement(window.Dashboard, {
                profile, connected, port, setPort, onToggleConn: toggleConn, logs,
                onUpdateGlobal: updateGlobal, onSetActive: setActive, storage, onSync: syncProfile,
              })}
              {view === "auto" && React.createElement(window.AutoSwitcher, {
                enabled: autoEnabled, onToggle: setAutoEnabled, activeCtx, setActiveCtx: setActiveCtx, regenKey,
              })}
              {view === "settings" && React.createElement(window.Settings, {
                settings, onChange: setSettings, advancedMode: advanced, onAdvancedMode: setAdvanced,
                widgetAlpha, onWidgetAlpha: setWidgetAlpha,
              })}
            </div>
          </div>
        </div>

        {/* FLOATING WIDGET */}
        {widgetOpen
          ? React.createElement(window.Widget, { ctxId: activeCtx, alpha: widgetAlpha, onClose: () => setWidgetOpen(false), onRegen: regenKey })
          : <button className="widget-fab" title="Show AI widget" onClick={() => setWidgetOpen(true)}><Icon name="sparkle" w="fill" /></button>}

        {/* COMMAND PALETTE */}
        {cmdkOpen && React.createElement(window.CommandPalette, { onClose: () => setCmdkOpen(false), onRun: runCmd })}
      </div>
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
})();
