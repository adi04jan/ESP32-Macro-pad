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

  // The macropad's USB identity (set by the firmware). Auto-detection matches on
  // VID/PID first (survives COM-number changes), then a product-name fallback.
  const MACROPAD = { vid: "303A", pid: "80C5" };
  const normId = (s) => (s || "").toString().toUpperCase().replace(/^0X/, "");
  function isMacropad(p) {
    if (!p) return false;
    if (normId(p.vendorId) === MACROPAD.vid && normId(p.productId) === MACROPAD.pid) return true;
    return /macropad/i.test(p.label || "") || /macropad/i.test(p.friendlyName || "");
  }
  const findMacropad = (list) => (list || []).find(isMacropad) || null;

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
    const [autoConnect, setAutoConnect] = useState(true);
    const [autoAssign, setAutoAssign] = useState(false);   // override keys with the focused app's top shortcuts
    const [autoAssignLabel, setAutoAssignLabel] = useState("");
    const [activeCtx, setActiveCtx] = useState("global");
    const [detectedApp, setDetectedApp] = useState("");
    const [widgetOpen, setWidgetOpen] = useState(false);   // separate always-on-top window

    const [cmdkOpen, setCmdkOpen] = useState(false);
    const [advanced, setAdvanced] = useState(false);
    const [settings, setSettings] = useState({ provider: "Ollama (Local)", key: "http://localhost:11434", model: "llama3" });
    const [widgetAlpha, setWidgetAlpha] = useState(0.98);

    const [aiRecs, setAiRecs] = useState({});      // ctxId -> [shortcut]
    const [aiBusy, setAiBusy] = useState(false);
    const [keyAiBusy, setKeyAiBusy] = useState(false);   // per-key "generate with AI"

    const [liveIdle, setLiveIdle] = useState("none");   // animation the on-screen mirror runs
    const simRef = useRef(null);
    if (!simRef.current && window.LedSim) simRef.current = new window.LedSim();

    const [saveStatus, setSaveStatus] = useState("idle");   // idle|pending|saving|saved|error
    const saveTimerRef = useRef(null);

    const profileRef = useRef(profile);
    profileRef.current = profile;

    // Latest values readable from intervals/callbacks without re-subscribing.
    const connectedRef = useRef(connected); connectedRef.current = connected;
    const autoConnectRef = useRef(autoConnect); autoConnectRef.current = autoConnect;
    const autoEnabledRef = useRef(autoEnabled); autoEnabledRef.current = autoEnabled;
    const autoAssignRef = useRef(autoAssign); autoAssignRef.current = autoAssign;
    const activeCtxRef = useRef(activeCtx); activeCtxRef.current = activeCtx;
    const appliedCtxRef = useRef(null);   // last context auto-assigned to the keys
    const manualDisconnectRef = useRef(false);   // user explicitly disconnected -> don't auto-reconnect

    const log = useCallback((text, opts = {}) => {
      setLogs((l) => [...l.slice(-200), { t: now(), text: String(text).replace(/\n$/, ""), ...opts }]);
    }, []);

    useEffect(() => { document.documentElement.setAttribute("data-theme", theme); localStorage.setItem("mp_theme", theme); }, [theme]);

    // Keep the always-on-top overlay showing the live key map. While auto-assign
    // is active the overlay is driven by applyAutoAssign instead.
    useEffect(() => { if (!autoAssignRef.current) api.widgetSetProfile(profile); }, [profile]);
    const toggleWidget = useCallback(() => { api.toggleWidget().then((vis) => setWidgetOpen(!!vis)); }, []);

    // Keep the on-screen LED mirror fed with the editor's colours + animation.
    useEffect(() => { if (simRef.current) simRef.current.setBaseFromKeys(profile.keys); }, [profile.keys]);
    useEffect(() => { if (simRef.current) simRef.current.setMode(liveIdle); }, [liveIdle]);
    useEffect(() => { setLiveIdle(profile.idle_animation || "none"); }, [profile.idle_animation]);

    // List ports, default the dropdown to the macropad if present, and (when
    // auto-connect is on and the user hasn't manually disconnected) open it.
    const refreshPorts = useCallback(() => {
      return api.listPorts().then((list) => {
        setPorts(list);
        const mp = findMacropad(list);
        setPort((cur) => cur || (mp && mp.path) || (list[0] && list[0].path) || "");
        if (mp && autoConnectRef.current && !connectedRef.current && !manualDisconnectRef.current) {
          setPort(mp.path);
          log(`Macropad found on ${mp.path} — auto-connecting…`, { cls: "ac" });
          api.connect(mp.path);
        }
      });
    }, [log]);

    // ---- boot: settings + ports + serial event stream ----
    useEffect(() => {
      api.getSettings().then((s) => {
        const isOllama = (s.provider || "").includes("Ollama");
        setSettings({ provider: s.provider, key: isOllama ? s.endpoint : s.key, model: s.model });
        setWidgetAlpha(s.widget_alpha != null ? s.widget_alpha : 0.98);
        setAutoEnabled(!!s.auto_switch_enabled); autoEnabledRef.current = !!s.auto_switch_enabled;
        setAutoAssign(!!s.auto_assign); autoAssignRef.current = !!s.auto_assign;
        const ac = s.auto_connect !== false;     // default ON
        autoConnectRef.current = ac; setAutoConnect(ac);
        refreshPorts();                            // first scan after the setting is known
      });
      const off = api.onEvent(({ type, data }) => {
        if (type === "log") log(data);
        else if (type === "open") {
          setConnected(true); api.fsinfo();
          // Sync the editor to the device's active profile (sequenced; no leak).
          const slot = profileRef.current.active || 1;
          api.switchProfile(slot)
            .then((p) => { if (p) { setProfile(fromDevice(p, slot)); setSaveStatus("idle"); } })
            .catch((e) => log(`Initial load error: ${e.message}`, { cls: "er" }));
        }
        else if (type === "disconnect") { setConnected(false); clearTimeout(saveTimerRef.current); setSaveStatus("idle"); }
        else if (type === "fs-info") setStorage(data);
        else if (type === "profile") {
          clearTimeout(saveTimerRef.current); saveTimerRef.current = null;
          setProfile((p) => fromDevice(data, p.active));
          setSaveStatus("idle");
          log("Profile synced from device.", { cls: "ok" });
        }
        else if (type === "leds") { if (simRef.current) simRef.current.setFrame(data); }   // exact live mirror
        else if (type === "key") { if (simRef.current) { const i = (data.key | 0) - 1; data.down ? simRef.current.keyDown(i) : simRef.current.keyUp(i); } }
        else if (type === "idle") { setLiveIdle(data.mode || "none"); }
        else if (type === "profile-active") {
          // The device switched profile on its own (touch pad). Reload that slot
          // into the editor so the UI + overlay reflect it. Skip if we initiated it.
          const n = data.profile | 0;
          if (n && n !== profileRef.current.active) {
            clearLive();
            flushSave().then(() => { updateGlobal("active", n); api.loadProfile(`profile${n}.json`); log(`Device switched to profile ${n}`, { cls: "ac" }); });
          }
        }
        else if (type === "active-context") {
          // Focused app changed -> switch the recommendation context, and (if
          // auto-assign is on) override the device keys with that app's shortcuts.
          setDetectedApp(data.process || "");
          if (autoEnabledRef.current && data.context) setActiveCtx(data.context);
          if (autoAssignRef.current && data.context && data.context !== appliedCtxRef.current) applyAutoAssign(data.context);
        }
      });
      // Poll for the macropad: refreshes the port list and auto-connects on
      // hotplug when enabled and not manually disconnected.
      const poll = setInterval(() => { refreshPorts(); }, 3000);
      return () => { off && off(); clearInterval(poll); };
    }, [refreshPorts, log]);

    // ⌘K
    useEffect(() => {
      const onKey = (e) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCmdkOpen((v) => !v); } };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, []);

    // ---- debounced live device pushes (instant preview without flooding) ----
    const liveTimers = useRef({});
    const pushLive = useCallback((key, fn, delay = 250) => {
      if (!connectedRef.current) return;
      clearTimeout(liveTimers.current[key]);
      liveTimers.current[key] = setTimeout(() => { try { fn(); } catch (_) {} }, delay);
    }, []);
    const clearLive = useCallback(() => {
      Object.values(liveTimers.current).forEach(clearTimeout);
      liveTimers.current = {};
    }, []);

    // ---- debounced auto-save (PC backup happens before the device write) ----
    const SAVE_DELAY = 1500;
    const doSave = useCallback(() => {
      saveTimerRef.current = null;
      const p = profileRef.current;
      if (!connectedRef.current) { setSaveStatus("idle"); return Promise.resolve(); }
      setSaveStatus("saving");
      return api.autoSave(p.active || 1, p)
        .then((r) => {
          if (r && r.ok) { setSaveStatus("saved"); setTimeout(() => setSaveStatus((s) => (s === "saved" ? "idle" : s)), 1600); }
          else { setSaveStatus("error"); log(`Auto-save failed: ${(r && r.error) || "unknown"}`, { cls: "er" }); }
        })
        .catch((e) => { setSaveStatus("error"); log(`Auto-save error: ${e.message}`, { cls: "er" }); });
    }, [log]);
    const scheduleSave = useCallback(() => {
      setSaveStatus("pending");
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(doSave, SAVE_DELAY);
    }, [doSave]);
    const flushSave = useCallback(() => {
      if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); return doSave(); }
      return Promise.resolve();
    }, [doSave]);

    // ---- profile mutations (realtime: live-push to device + schedule autosave) ----
    // Build the new profile synchronously from the latest committed state so the
    // live push carries the *new* values (profileRef updates only on re-render).
    const mutateKey = (id, fn) => {
      const np = clone(profileRef.current);
      const k = np.keys.find((x) => x.id === id);
      if (k) fn(k);
      setProfile(np);
      if (k) pushLive(`key${id}`, () => api.setKey(id, k.actions));   // debounced live preview
      scheduleSave();
    };
    const updateGlobal = (key, val) => {
      setProfile({ ...profileRef.current, [key]: val });
      if (key !== "active") scheduleSave();
    };
    const renameKey = (name) => mutateKey(selectedId, (k) => (k.name = name));
    const changeAction = (i, na) => mutateKey(selectedId, (k) => (k.actions[i] = na));
    const deleteAction = (i) => mutateKey(selectedId, (k) => k.actions.splice(i, 1));
    const addAction = (a) => mutateKey(selectedId, (k) => k.actions.push(a));
    const reorder = (from, to) => mutateKey(selectedId, (k) => { const [m] = k.actions.splice(from, 1); k.actions.splice(to, 0, m); });
    const setGlow = (id, rgb) => {
      const np = clone(profileRef.current);
      const k = np.keys.find((x) => x.id === id);
      if (k) k.glow = rgb;
      setProfile(np);
      if (simRef.current) simRef.current.setBase(id - 1, rgb);
      const c = rgb || [0, 0, 0];
      pushLive(`led${id}`, () => api.setLed(id, c[0], c[1], c[2]), 120);   // debounced live colour
      scheduleSave();
    };
    // Idle animation: update profile + on-screen mirror + push live to device + autosave.
    const setIdleAnim = (v) => {
      updateGlobal("idle_animation", v);
      setLiveIdle(v);
      if (connectedRef.current) api.setIdle(v);
    };

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
      if (connected) { manualDisconnectRef.current = true; api.disconnect(); return; }
      if (!port) { log("Select a port first.", { cls: "er" }); return; }
      manualDisconnectRef.current = false;   // manual connect re-enables auto-reconnect
      log(`Opening ${port}…`);
      api.connect(port);
    }, [connected, port, log]);

    const onToggleAutoConnect = useCallback((v) => {
      setAutoConnect(v); autoConnectRef.current = v;
      api.setSettings({ auto_connect: v });
      if (v) { manualDisconnectRef.current = false; refreshPorts(); }   // try to grab the device now
    }, [refreshPorts]);

    // Reload the active slot from the device, discarding unsaved in-editor edits.
    const reloadProfile = () => {
      const slot = profileRef.current.active || 1;
      clearLive();
      if (saveTimerRef.current) { clearTimeout(saveTimerRef.current); saveTimerRef.current = null; }
      log(`Reloading profile ${slot} from device…`, { prompt: true });
      api.loadProfile(`profile${slot}.json`);
    };

    // Switch which profile you're editing: persist the current one first, then
    // make the device active on slot n and reload its data into the editor so
    // the editor always mirrors the device (fixes editor/device drift).
    const setActive = (n) => {
      clearLive();                        // drop pending pushes aimed at the old slot
      flushSave().then(() => {            // persist current slot before switching
        updateGlobal("active", n);
        if (connectedRef.current) {
          api.switchProfile(n)
            .then((p) => {
              if (p) { setProfile(fromDevice(p, n)); setSaveStatus("idle"); log(`Editing profile ${n}`, { cls: "ac" }); }
              else log(`Could not load profile ${n} from device.`, { cls: "er" });
            })
            .catch((e) => log(`Profile switch error: ${e.message}`, { cls: "er" }));
        }
      });
    };

    const backupAll = () => {
      if (!connectedRef.current) { log("Connect a device to back up.", { cls: "er" }); return; }
      setSaveStatus("saving");
      api.backupAll()
        .then((r) => {
          if (r && r.ok) { log(`Backed up all profiles → ${r.path} (${r.count} files)`, { cls: "ok" }); setSaveStatus("saved"); setTimeout(() => setSaveStatus("idle"), 1600); }
          else { log(`Backup failed: ${(r && r.error) || "unknown"}`, { cls: "er" }); setSaveStatus("error"); }
        })
        .catch((e) => { log(`Backup error: ${e.message}`, { cls: "er" }); setSaveStatus("error"); });
    };

    const importDisk = () => api.importProfile().then((r) => {
      if (r && r.ok) { setProfile((p) => fromDevice(r.profile, p.active)); log(`Imported ${r.path}`, { cls: "ok" }); }
      else if (r && r.error) log(`Import failed: ${r.error}`, { cls: "er" });
    });
    const exportDisk = () => api.exportProfile(profileRef.current).then((r) => {
      if (r && r.ok) log(`Exported ${r.path}`, { cls: "ok" });
      else if (r && r.error) log(`Export failed: ${r.error}`, { cls: "er" });
    });

    // ---- AI + usage-ranked recommendations ----
    const recsFor = (ctxId) => aiRecs[ctxId] || [];
    // Pull the context's library, usage-ranked (most-pressed first), into view.
    const loadRecs = useCallback((ctxId) => {
      api.getRankedTemplates(ctxId, 8).then((items) => {
        if (Array.isArray(items)) setAiRecs((prev) => ({ ...prev, [ctxId]: items }));
      }).catch(() => {});
    }, []);

    const regenKey = (ctxId, kn) => {
      if (aiBusy) return;
      setAiBusy(true);
      log(`AI: generating ${kn && kn !== "all" ? "key " + kn : "shortcuts"} for [${ctxId}]…`, { cls: "ac" });
      const keyNums = kn && kn !== "all" ? [kn] : null;
      api.aiShortcuts({ context: ctxId, existing: recsFor(ctxId), count: 4, keyNums })
        .then((items) => {
          setAiBusy(false);
          if (!items || !items.length) { log("AI: no valid shortcuts produced.", { cls: "er" }); return; }
          // Persist, then re-load so the new ones take their usage-ranked place.
          api.addTemplates(ctxId, items).then((n) => { log(`AI: added ${n} shortcut(s) for [${ctxId}].`, { cls: "ok" }); loadRecs(ctxId); });
        })
        .catch((e) => { setAiBusy(false); log(`AI error: ${e.message}`, { cls: "er" }); });
    };
    // Auto-refresh: AI-regenerate suggestions for the active context (the least-
    // used naturally sink in the usage ranking once re-loaded).
    const aiRefresh = useCallback(() => {
      if (aiBusy || !autoEnabledRef.current) return;
      regenKey(activeCtxRef.current, "all");
    }, [aiBusy]);

    // Load recs for the active context; re-rank periodically as usage accrues;
    // AI-refresh on a slow cadence when auto-switch is on.
    useEffect(() => { loadRecs(activeCtx); }, [activeCtx, loadRecs]);
    useEffect(() => {
      const rerank = setInterval(() => loadRecs(activeCtxRef.current), 20000);
      const refresh = setInterval(aiRefresh, 6 * 60 * 1000);
      return () => { clearInterval(rerank); clearInterval(refresh); };
    }, [loadRecs, aiRefresh]);

    // ---- auto-assign: override the device keys with the focused app's top
    // shortcuts (live in device RAM + overlay only — saved profiles untouched).
    const applyAutoAssign = useCallback((ctxId) => {
      if (!autoAssignRef.current || !connectedRef.current || !ctxId) return;
      api.getRankedTemplates(ctxId, 12).then((items) => {
        if (!Array.isArray(items)) return;
        const keys = [];
        for (let i = 1; i <= 12; i++) {
          const it = items[i - 1];
          keys.push({ id: i, name: it ? it.description : "", glow: null, actions: it ? it.actions : [] });
          api.setKey(i, it ? it.actions : []);             // live to device RAM (not persisted)
        }
        const label = (M.CONTEXTS.find((c) => c.id === ctxId) || {}).label || ctxId;
        const p = profileRef.current;
        const autoProfile = { profile_name: "Auto · " + label, idle_animation: p.idle_animation, default_delay: p.default_delay, active: p.active, keys };
        api.widgetSetProfile(autoProfile);                  // overlay reflects the live keys
        if (simRef.current) simRef.current.setBaseFromKeys(keys);
        appliedCtxRef.current = ctxId;
        setAutoAssignLabel(label);
        log(`Auto-assigned ${keys.filter((k) => k.actions.length).length} ${label} shortcuts to the keys (live).`, { cls: "ac" });
      }).catch(() => {});
    }, [log]);

    // Restore the device + overlay to the saved active profile.
    const restoreSavedProfile = useCallback(() => {
      appliedCtxRef.current = null; setAutoAssignLabel("");
      if (!connectedRef.current) return;
      const slot = profileRef.current.active || 1;
      api.switchProfile(slot).then((p) => { if (p) { const fp = fromDevice(p, slot); setProfile(fp); api.widgetSetProfile(fp); } }).catch(() => {});
    }, []);

    const onToggleAutoAssign = useCallback((v) => {
      setAutoAssign(v); autoAssignRef.current = v;
      api.setSettings({ auto_assign: v });
      if (v) {
        if (!autoEnabledRef.current) { setAutoEnabled(true); autoEnabledRef.current = true; api.setSettings({ auto_switch_enabled: true }); }
        applyAutoAssign(activeCtxRef.current);
      } else restoreSavedProfile();
    }, [applyAutoAssign, restoreSavedProfile]);
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
      else if (kind === "widget") toggleWidget();
      else if (kind === "advanced") setAdvanced((v) => !v);
      else if (kind === "connect") toggleConn();
      else if (kind === "test") { setView("editor"); testKey(); }
      else if (kind === "key") { setView("editor"); setSelectedId(arg); }
    };

    // Describe a macro in words -> AI builds + validates the action sequence for the selected key.
    const aiFillKey = (desc) => {
      if (!desc || !desc.trim() || keyAiBusy) return;
      setKeyAiBusy(true);
      log(`AI: building macro for K${selectedId}: "${desc.trim()}"…`, { cls: "ac" });
      api.aiActions(desc.trim())
        .then((actions) => {
          if (actions && actions.length) {
            mutateKey(selectedId, (k) => { k.actions = actions; });
            log(`AI: bound ${actions.length} action(s) to K${selectedId}.`, { cls: "ok" });
          } else log("AI: couldn't produce a valid macro — try rephrasing.", { cls: "er" });
        })
        .catch((e) => log(`AI error: ${e.message}`, { cls: "er" }))
        .finally(() => setKeyAiBusy(false));
    };

    const builderProps = { onRename: renameKey, onChangeAction: changeAction, onDeleteAction: deleteAction,
      onAddAction: addAction, onReorder: reorder, onTest: testKey, runningIndex,
      onAiGenerate: aiFillKey, aiBusy: keyAiBusy };

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
            {autoAssign && autoAssignLabel &&
              <span className="chip accent" title="Keys are auto-assigned to the focused app (live, not saved)">
                <Icon name="magic-wand" w="bold" /> Auto · {autoAssignLabel}</span>}
            <button className={`conn-pill ${connected ? "on" : ""}`} onClick={() => setView("dashboard")}>
              <span className="conn-dot" /> {connected ? (port || "device") + " · live" : "Offline"}
            </button>
            <div style={{ width: 1, height: 26, background: "var(--line)" }} />
            <button className="btn sm" onClick={() => setCmdkOpen(true)}>
              <Icon name="magnifying-glass" w="bold" /> <span className="kbd" style={{ marginLeft: 2 }}>⌘K</span>
            </button>
            <IconBtn icon="code" w="bold" title="Advanced mode"
              onClick={() => setAdvanced((v) => !v)} style={advanced ? { color: "var(--accent)", background: "var(--hover)" } : null} />
            <IconBtn icon="app-window" w="bold" title="Toggle always-on-top key overlay"
              onClick={toggleWidget} style={widgetOpen ? { color: "var(--accent)" } : null} />
          </header>

          <div className="view-scroll" key={view}>
            <div className="view-pad">
              {view === "editor" && React.createElement(window.KeyEditor, { profile, selectedId, onSelect: setSelectedId, onSetGlow: setGlow, sim: simRef.current, liveIdle, pressingId, advanced, builderProps })}
              {view === "dashboard" && React.createElement(window.Dashboard, {
                profile, connected, port, setPort, ports, onRefreshPorts: refreshPorts, onToggleConn: toggleConn, logs,
                onUpdateGlobal: updateGlobal, onSetActive: setActive, storage, onReload: reloadProfile, onImport: importDisk, onExport: exportDisk,
                autoConnect, onToggleAutoConnect, isMacropad, onSetIdle: setIdleAnim, saveStatus, onBackupAll: backupAll,
              })}
              {view === "auto" && React.createElement(window.AutoSwitcher, {
                enabled: autoEnabled, onToggle: onToggleAuto, activeCtx, setActiveCtx, regenKey, recsFor, onPush: pushRec, busy: aiBusy, detectedApp,
                autoAssign, onToggleAutoAssign,
              })}
              {view === "settings" && React.createElement(window.Settings, {
                settings, onChange: onChangeSettings, advancedMode: advanced, onAdvancedMode: setAdvanced,
                widgetAlpha, onWidgetAlpha, onTest: () => api.aiTest(),
              })}
            </div>
          </div>
        </div>

        {cmdkOpen && React.createElement(window.CommandPalette, { onClose: () => setCmdkOpen(false), onRun: runCmd })}
      </div>
    );
  }

  ReactDOM.createRoot(document.getElementById("root")).render(<App />);
})();
