/* ============================================================
   MACROPAD STUDIO — Dashboard (device, profiles, console)
   ============================================================ */
(function () {
  const { useState, useRef, useEffect } = React;
  const { Icon, Btn, IconBtn, Select, Field, Panel, Toggle } = window.UI;
  const M = window.MACRO;

  const SAVE_LABEL = { pending: "Editing…", saving: "Saving…", saved: "Saved ✓", error: "Save failed" };

  function Dashboard({ profile, connected, port, setPort, ports = [], onRefreshPorts, onToggleConn, logs, onUpdateGlobal, onSetActive, storage, onReload, onImport, onExport, autoConnect, onToggleAutoConnect, isMacropad, onSetIdle, saveStatus, onBackupAll }) {
    const portOpts = ports.length ? ports.map((p) => ({ value: p.path, label: p.label || p.path })) : [{ value: "", label: "No ports found" }];
    const detected = isMacropad ? ports.find((p) => isMacropad(p)) : null;
    const saveChip = saveStatus && saveStatus !== "idle"
      ? <span className={`chip ${saveStatus === "saved" ? "accent" : saveStatus === "error" ? "" : ""}`}>{SAVE_LABEL[saveStatus] || ""}</span>
      : null;
    const consoleRef = useRef(null);
    useEffect(() => {
      if (consoleRef.current) consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }, [logs]);

    const usedPct = storage.total ? storage.used / storage.total : 0;

    return (
      <div className="view-enter">
        <div className="mb20">
          <div className="page-title">Dashboard</div>
          <div className="page-sub">Connect your macropad, sync profiles, and watch the live device log.</div>
        </div>

        <div className="dash-grid">
          <div className="col" style={{ gap: 18 }}>
            {/* connection */}
            <Panel title="Device" icon="usb" sub="Serial connection">
              <div className="row between mb8" style={{ alignItems: "center" }}>
                <div>
                  <div className="section-label">Auto-connect to macropad</div>
                  <div className="mono fs12 faint">
                    {detected ? `Found: ${detected.path}${detected.friendlyName ? " · " + detected.friendlyName : ""}`
                              : "Macropad not detected"}
                  </div>
                </div>
                <Toggle on={!!autoConnect} onChange={onToggleAutoConnect} />
              </div>
              <Field label="Port (manual override)">
                <Select value={port} options={portOpts} onChange={setPort} />
              </Field>
              <div className="row" style={{ gap: 8, marginTop: 14 }}>
                <Btn className="grow" variant={connected ? "danger" : "primary"} size="lg"
                  icon={connected ? "plugs" : "plugs-connected"} onClick={onToggleConn}>
                  {connected ? "Disconnect" : "Connect"}
                </Btn>
                <IconBtn icon="arrow-clockwise" title="Refresh ports" onClick={onRefreshPorts} />
              </div>
              <div className={`conn-pill ${connected ? "on" : ""}`} style={{ marginTop: 14, width: "100%", justifyContent: "center" }}>
                <span className="conn-dot" /> {connected ? "Live · " + port.split(" ")[0] : (autoConnect ? "Searching…" : "Not connected")}
              </div>
            </Panel>

            {/* profiles */}
            <Panel title="Profiles" icon="stack" sub="Edit any slot · auto-saves live" right={saveChip}>
              <div className="profile-pills">
                {[1, 2, 3].map((n) => (
                  <button key={n} className={`profile-pill ${profile.active === n ? "active" : ""}`} onClick={() => onSetActive(n)} title={connected ? `Edit profile ${n} (switches the device)` : `Edit profile ${n}`}>
                    <div className="pn">P{n}</div>
                    <div className="pd">{profile.active === n ? "editing" : "slot " + n}</div>
                  </button>
                ))}
              </div>
              <div className="mono fs12 faint" style={{ marginTop: 10 }}>
                {connected ? "Edits save to the device automatically (~1.5s) with a PC backup before each save." : "Connect to edit live; changes auto-save when connected."}
              </div>
              <div className="row" style={{ gap: 8, marginTop: 12 }}>
                <Btn className="grow" size="sm" icon="download-simple" disabled={!connected} onClick={onReload}>Reload</Btn>
                <Btn className="grow" size="sm" icon="archive-box" disabled={!connected} onClick={onBackupAll}>Backup all</Btn>
              </div>

              <div className="divider" />
              <div className="row between mb8">
                <span className="section-label">Flash storage</span>
                <span className="mono fs12 faint">{storage.total ? (storage.used / 1024).toFixed(1) + " / " + (storage.total / 1024).toFixed(0) + " KB" : "—"}</span>
              </div>
              <div className="storage-bar"><div className="storage-fill" style={{ width: (usedPct * 100) + "%" }} /></div>
              <div className="row" style={{ gap: 8, marginTop: 14 }}>
                <Btn className="grow" size="sm" icon="file-arrow-down" onClick={onImport}>Import .json</Btn>
                <Btn className="grow" size="sm" icon="file-arrow-up" onClick={onExport}>Export .json</Btn>
              </div>
            </Panel>
          </div>

          {/* console + global settings */}
          <div className="col" style={{ gap: 18 }}>
            <Panel title="Profile settings" icon="sliders-horizontal" sub="Applies to the whole profile">
              <div className="row gap14 wrap">
                <Field label="Profile name"><input className="input" value={profile.profile_name}
                  onChange={(e) => onUpdateGlobal("profile_name", e.target.value)} /></Field>
              </div>
              <div className="row gap14 wrap" style={{ marginTop: 14 }}>
                <div className="grow"><Field label="Idle animation">
                  <Select value={profile.idle_animation} options={M.IDLE_ANIMATIONS}
                    onChange={(v) => (onSetIdle ? onSetIdle(v) : onUpdateGlobal("idle_animation", v))} /></Field></div>
                <div className="grow"><Field label="Default delay (ms)">
                  <input className="input mono" type="number" value={profile.default_delay}
                    onChange={(e) => onUpdateGlobal("default_delay", parseInt(e.target.value || "0"))} /></Field></div>
              </div>
            </Panel>

            <Panel title="Device console" icon="terminal-window"
              right={<span className={`chip ${connected ? "accent" : ""}`}>{connected ? "streaming" : "idle"}</span>}>
              <div className="console" ref={consoleRef}>
                {logs.length === 0 && <div className="faint">Waiting for device…</div>}
                {logs.map((l, i) => (
                  <div className="ln" key={i}>
                    <span className="t">{l.t}</span>
                    {l.prompt ? <span className="prompt">macropad:$</span> : null}
                    <span className={l.cls || ""}>{l.text}</span>
                  </div>
                ))}
              </div>
            </Panel>
          </div>
        </div>
      </div>
    );
  }

  window.Dashboard = Dashboard;
})();
