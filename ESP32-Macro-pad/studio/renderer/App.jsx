/* ============================================================
   MACROPAD STUDIO — App shell + state (wired to the real device via window.api)
   ============================================================ */
(function () {
  const { useState, useEffect, useRef, useCallback } = React;
  const { Icon, IconBtn, Btn } = window.UI;
  const M = window.MACRO;
  const api = window.api;

  const NAV = [
    { id: "editor", label: "Editor", icon: "sliders" },
    { id: "dashboard", label: "Device", icon: "gauge" },
    { id: "auto", label: "AI", icon: "sparkle" },
    { id: "settings", label: "Settings", icon: "gear-six" },
  ];
  const VIEW_LABEL = { editor: "Key Editor", dashboard: "Dashboard", auto: "Auto-Switcher", settings: "Settings" };

  const clone = (o) => JSON.parse(JSON.stringify(o));
  const now = () => new Date().toTimeString().slice(0, 8);

  // device profile JSON -> UI profile shape (ensures 12 keys, glow from led_color)
  function fromDevice(p, activeSlot) {
    const byId = {};
    (p.keys || []).forEach((k) => (byId[k.id] = k));
    const keys = [];
    for (let i = 1; i <= 12; i++) {
      const k = byId[i] || {};
      keys.push({ id: i, name: k.name || "", glow: k.led_color || null, actions: Array.isArray(k.actions) ? k.actions : [] });
    }
    return {
      profile_name: p.profile_name || "Profile",
      idle_animation: p.idle_animation || "none",
      default_delay: p.default_delay != null ? p.default_delay : 30,
      active: activeSlot || 1,
      keys,
    };
  }

  function App() {
    const [theme, setTheme] = useState(() => localStorage.getItem("mp_theme") || "dark");
    const [view, setView] = useState("editor");
    const [profile, setProfile] = useState(() => clone(M.SEED));
    const [selectedId, setSelectedId] = useState(1);
    const [pressingId, setPressingId] = useState(null);
    const [runningIndex, setRunningIndex] = useState(null);

    const [connected, setConnected] = useState(false);
    const [ports, setPorts] = useState([]);
    const [port, setPort] = useState("");
    const [logs, setLogs] = useState([]);
    const [storage, setStorage] = useState({ total: 0, used: 0 });

    const [autoEnabled, setAutoEnabled] = useState(false);
    const [activeCtx, setActiveCtx] = useState("vscode");
    const [widgetOpen, setWidgetOpen] = useState(true);

    const [cmdkOpen, setCmdkOpen] = useState(false);
    const [advanced, setAdvanced] = useState(false);
    const [settings, setSettings] = useState({ provider: "Ollama (Local)", key: "http://localhost:11434", model: "llama3" });
    const [widgetAlpha, setWidgetAlpha] = useState(0.98);

    const [aiRecs, setAiRecs] = useState({});      // ctxId -> [shortcut]
    const [aiBusy, setAiBusy] = useState(false);

    const profileRef = useRef(profile);
    profileRef.current = profile;

    const log = useCallback((text, opts = {}) => {
      setLogs((l) => [...l.slice(-200), { t: now(), text: String(text).replace(/\n$/, ""), ...opts }]);
    }, []);

    useEffect(() => { document.documentElement.setAttribute("data-theme", theme); localStorage.setItem("mp_theme", theme); }, [theme]);

    const refreshPorts = useCallback(() => {
      api.listPorts().then((list) => { setPorts(list); setPort((cur) => cur || (list[0] && list[0].path) || ""); });
    }, []);

    // ---- boot: settings + ports + serial event stream ----
    useEffect(() => {
      api.getSettings().then((s) => {
        const isOllama = (s.provider || "").includes("Ollama");
        setSettings({ provider: s.provider, key: isOllama ? s.endpoint : s.key, model: s.model });
        setWidgetAlpha(s.widget_alpha != null ? s.widget_alpha : 0.98);
        setAutoEnabled(!!s.auto_switch_enabled);
      });
      refreshPorts();
      const off = api.onEvent(({ type, data }) => {
        if (type === "log") log(data);
        else if (type === "open") { setConnected(true); api.fsinfo(); }
        else if (type === "disconnect") setConnected(false);
        else if (type === "fs-info") setStorage(data);
        else if (type === "profile") { setProfile((p) => fromDevice(data, p.active)); log("Profile loaded into editor.", { cls: "ok" }); }
      });
      return off;
    }, []);

    // ⌘K
    useEffect(() => {
      const onKey = (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmdkOpen((v) => !v); } };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, []);

    // ---- profile mutations ----
    const mutateKey = (id, fn) => setProfile((p) => { const np = clone(p); fn(np.keys.find((x) => x.id === id)); return np; });
    const updateGlobal = (key, val) => setProfile((p) => ({ ...p, [key]: val }));
    const renameKey = (name) => mutateKey(selectedId, (k) => (k.name = name));
    const changeAction = (i, na) => mutateKey(selectedId, (k) => (k.actions[i] = na));
    const deleteAction = (i) => mutateKey(selectedId, (k) => k.actions.splice(i, 1));
    const addAction = (a) => mutateKey(selectedId, (k) => k.actions.push(a));
    const reorder = (from, to) => mutateKey(selectedId, (k) => { const [m] = k.actions.splice(from, 1); k.actions.splice(to, 0, m); });

    // ---- test animation (visual) + push to device ----
    const testRef = useRef(false);
    const testKey = useCallback(() => {
      if (testRef.current) return;
      const key = profileRef.current.keys.find((k) => k.id === selectedId);
      if (!key || !key.actions.length) return;
      testRef.current = true; setPressingId(selectedId);
      if (connected) { api.setKey(selectedId, key.actions); log(`Pushed key ${selectedId} (${key.name}) to device`, { prompt: true, cls: "ac" }); }
      let i = 0;
      const step = () => {
        if (i >= key.actions.length) { setRunningIndex(null); setPressingId(null); testRef.current = false; return; }
        setRunningIndex(i);
        const a = key.actions[i];
        const dur = a.type === "delay" ? Math.max(180, Math.min(900, a.ms || 100)) : 380;
        i++; setTimeout(step, dur);
      };
      step();
    }, [selectedId, connected, log]);

    // ---- device ----
    const toggleConn = useCallback(() => {
      if (connected) { api.disconnect(); return; }
      if (!port) { log("Select a port first.", { cls: "er" }); return; }
      log(`Opening ${port}…`);
      api.connect(port);
    }, [connected, port, log]);

    const syncProfile = (mode) => {
      const fname = `profile${profileRef.current.active}.json`;
      if (mode === "save") {
        log(`Uploading ${fname}…`, { prompt: true });
        api.saveProfile(fname, profileRef.current).then((ok) => {
          if (ok) { log("Upload complete ✓", { cls: "ok" }); api.setActive(profileRef.current.active); setTimeout(() => api.fsinfo(), 600); }
        });
      } else { log(`Fetching ${fname}…`, { prompt: true }); api.loadProfile(fname); }
    };

    const setActive = (n) => { updateGlobal("active", n); if (connected) { api.setActive(n); log(`setprofile ${n}`, { prompt: true, cls: "ac" }); } };

    const importDisk = () => api.importProfile().then((r) => {
      if (r && r.ok) { setProfile((p) => fromDevice(r.profile, p.active)); log(`Imported ${r.path}`, { cls: "ok" }); }
      else if (r && r.error) log(`Import failed: ${r.error}`, { cls: "er" });
    });
    const exportDisk = () => api.exportProfile(profileRef.current).then((r) => {
      if (r && r.ok) log(`Exported ${r.path}`, { cls: "ok" });
      else if (r && r.error) log(`Export failed: ${r.error}`, { cls: "er" });
    });

    // ---- AI ----
    const recsFor = (ctxId) => aiRecs[ctxId] || (M.CONTEXTS.find((c) => c.id === ctxId) || {}).recs || [];
    const regenKey = (ctxId, kn) => {
      if (aiBusy) return;
      setAiBusy(true);
      log(`AI: generating ${kn && kn !== "all" ? "key " + kn : "shortcuts"} for [${ctxId}]…`, { cls: "ac" });
      const keyNums = kn && kn !== "all" ? [kn] : null;
      api.aiShortcuts({ context: ctxId, existing: recsFor(ctxId), count: 4, keyNums }).then((items) => {
        setAiBusy(false);
        if (!items || !items.length) { log("AI: no valid shortcuts produced.", { cls: "er" }); return; }
        setAiRecs((prev) => {
          const cur = prev[ctxId] ? [...prev[ctxId]] : [];
          items.forEach((it, i) => {
            const slot = it.key_num || ((i % 4) + 1);
            const idx = cur.findIndex((c) => (c.key_num || 0) === slot);
            const rec = { ...it, key_num: slot };
            if (idx >= 0) cur[idx] = rec; else cur.push(rec);
          });
          return { ...prev, [ctxId]: cur.slice(0, 8) };
        });
        api.addTemplates(ctxId, items).then((n) => log(`AI: added ${n} validated shortcut(s) for [${ctxId}].`, { cls: "ok" }));
      });
    };
    const pushRec = (rec) => {
      if (!connected) { log("Connect a device first to push.", { cls: "er" }); return; }
      if (rec.key_num) { api.setKey(rec.key_num, rec.actions); log(`Pushed "${rec.description}" to K${rec.key_num}`, { cls: "ac" }); }
    };

    // ---- settings ----
    const onChangeSettings = (s) => {
      setSettings(s);
      const isOllama = (s.provider || "").includes("Ollama");
      api.setSettings({ provider: s.provider, model: s.model, [isOllama ? "endpoint" : "key"]: s.key });
    };
    const onWidgetAlpha = (a) => { setWidgetAlpha(a); api.setSettings({ widget_alpha: a }); };
    const onToggleAuto = (v) => { setAutoEnabled(v); api.setSettings({ auto_switch_enabled: v }); };

    // ---- command palette ----
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

        <div className="main">
          <header className="topbar">
            <div className="tb-title"><b>{VIEW_LABEL[view]}</b><span>macropad-studio · v2</span></div>
            <div className="tb-spacer" />
            <button className={`conn-pill ${connected ? "on" : ""}`} onClick={() => setView("dashboard")}>
              <span className="conn-dot" /> {connected ? (port || "device") + " · live" : "Offline"}
            </button>
            <div style={{ width: 1, height: 26, background: "var(--line)" }} />
            <button className="btn sm" onClick={() => setCmdkOpen(true)}>
              <Icon name="magnifying-glass" w="bold" /> <span className="kbd" style={{ marginLeft: 2 }}>⌘K</span>
            </button>
            <IconBtn icon="code" w="bold" title="Advanced mode"
              onClick={() => setAdvanced((v) => !v)} style={advanced ? { color: "var(--accent)", background: "var(--hover)" } : null} />
            <IconBtn icon="app-window" w="bold" title="Toggle AI widget"
              onClick={() => setWidgetOpen((v) => !v)} style={widgetOpen ? { color: "var(--accent)" } : null} />
          </header>

          <div className="view-scroll" key={view}>
            <div className="view-pad">
              {view === "editor" && React.createElement(window.KeyEditor, { profile, selectedId, onSelect: setSelectedId, pressingId, advanced, builderProps })}
              {view === "dashboard" && React.createElement(window.Dashboard, {
                profile, connected, port, setPort, ports, onRefreshPorts: refreshPorts, onToggleConn: toggleConn, logs,
                onUpdateGlobal: updateGlobal, onSetActive: setActive, storage, onSync: syncProfile, onImport: importDisk, onExport: exportDisk,
              })}
              {view === "auto" && React.createElement(window.AutoSwitcher, {
                enabled: autoEnabled, onToggle: onToggleAuto, activeCtx, setActiveCtx, regenKey, recsFor, onPush: pushRec, busy: aiBusy,
              })}
              {view === "settings" && React.createElement(window.Settings, {
                settings, onChange: onChangeSettings, advancedMode: advanced, onAdvancedMode: setAdvanced,
                widgetAlpha, onWidgetAlpha, onTest: () => api.aiTest(),
              })}
            </div>
          </div>
        </div>

        {widgetOpen
          ? React.createElement(window.Widget, { ctxId: activeCtx, alpha: widgetAlpha, onClose: () => setWidgetOpen(false), onRegen: regenKey, recsFor, onPush: pushRec })
          : <button className="widget-fab" title="Show AI widget" onClick={() => setWidgetOpen(true)}><Icon name="sparkle" w="fill" /></button>}

        {cmdkOpen && React.createElement(window.CommandPalette, { onClose: () => setCmdkOpen(false), onRun: runCmd })}
      </div>
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
})();
