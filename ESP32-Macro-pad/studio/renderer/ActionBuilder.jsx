/* ============================================================
   MACROPAD STUDIO — Action Builder
   ============================================================ */
(function () {
  const { useState, useRef, useEffect } = React;
  const { Icon, Btn, IconBtn, Select, Collapse, ActionTile, useDismiss, rgbCss } = window.UI;
  const M = window.MACRO;

  const SWATCHES = [
    [255,138,76],[255,93,108],[255,110,199],[192,107,255],
    [91,140,255],[54,198,255],[54,230,200],[80,230,160],
    [255,200,60],[255,255,255],[120,120,140],[20,20,28],
  ];

  function hexToRgb(h) {
    const n = parseInt(h.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function rgbToHex(c) {
    return "#" + c.map((x) => Math.max(0, Math.min(255, x | 0)).toString(16).padStart(2, "0")).join("");
  }

  // ---- keycombo recorder ----
  function mapKey(e) {
    const k = e.key;
    const map = {
      Control: "LEFT_CTRL", Shift: "LEFT_SHIFT", Alt: "LEFT_ALT", Meta: "LEFT_GUI",
      Enter: "ENTER", Escape: "ESC", Backspace: "BACKSPACE", Tab: "TAB", " ": "SPACE",
      ArrowUp: "UP_ARROW", ArrowDown: "DOWN_ARROW", ArrowLeft: "LEFT_ARROW", ArrowRight: "RIGHT_ARROW",
      "-": "MINUS", "=": "EQUAL", "`": "TILDE",
    };
    if (map[k]) return map[k];
    if (k.length === 1) return k.toUpperCase();
    if (/^F\d{1,2}$/.test(k)) return k;
    return k.toUpperCase();
  }

  function Recorder({ initial, onSave, onClose }) {
    const [keys, setKeys] = useState([]);
    useEffect(() => {
      const onKey = (e) => {
        e.preventDefault();
        const mapped = mapKey(e);
        setKeys((prev) => (prev.includes(mapped) ? prev : [...prev, mapped]));
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, []);
    return (
      <div className="cmdk-overlay" onMouseDown={onClose}>
        <div className="cmdk" style={{ width: 420, alignItems: "stretch" }} onMouseDown={(e) => e.stopPropagation()}>
          <div style={{ padding: 28, textAlign: "center" }}>
            <div className="section-label" style={{ marginBottom: 14 }}>Recording keys — press your combo</div>
            <div className="row" style={{ justifyContent: "center", gap: 8, minHeight: 40, flexWrap: "wrap" }}>
              {keys.length === 0 && <span className="faint">Listening…</span>}
              {keys.map((k, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <span className="faint">+</span>}
                  <span className="kbd" style={{ height: 32, fontSize: 13, minWidth: 32 }}>{M.glyph(k)}</span>
                </React.Fragment>
              ))}
            </div>
            <div className="row" style={{ justifyContent: "center", gap: 10, marginTop: 24 }}>
              <Btn variant="ghost" onClick={() => setKeys([])} icon="arrow-counter-clockwise">Reset</Btn>
              <Btn variant="primary" icon="check" onClick={() => { onSave(keys); onClose(); }} disabled={!keys.length}>Save Combo</Btn>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- per-type value editor ----
  function ValueEditor({ action, onChange }) {
    const t = action.type;
    const [rec, setRec] = useState(false);
    const set = (patch) => onChange({ ...action, ...patch });

    if (t === "text") {
      return <input className="input mono" value={action.value || ""} placeholder="Text to type…"
        onChange={(e) => set({ value: e.target.value })} />;
    }
    if (t === "keycombo") {
      const keys = action.keys || [];
      return (
        <div className="row grow" style={{ gap: 8 }}>
          <div className="row grow wrap" style={{ gap: 5, minHeight: 32 }}>
            {keys.length === 0 && <span className="faint fs12">No keys yet</span>}
            {keys.map((k, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span className="faint" style={{ fontSize: 11 }}>+</span>}
                <span className="kbd">{M.glyph(k)}</span>
              </React.Fragment>
            ))}
          </div>
          <Btn size="sm" icon="record" onClick={() => setRec(true)}>Record</Btn>
          {rec && <Recorder onSave={(ks) => set({ keys: ks })} onClose={() => setRec(false)} />}
        </div>
      );
    }
    if (t === "key" || t === "hold" || t === "release") {
      const val = action.value || action.key || "ENTER";
      return <Select className="grow" value={val} options={M.KEYS}
        onChange={(v) => set(t === "hold" ? { key: v } : { value: v })} />;
    }
    if (t === "delay") {
      return (
        <div className="row grow" style={{ gap: 8 }}>
          <input className="input mono" type="number" min="0" style={{ maxWidth: 140 }}
            value={action.ms != null ? action.ms : 30} onChange={(e) => set({ ms: parseInt(e.target.value || "0") })} />
          <span className="faint fs13">milliseconds</span>
        </div>
      );
    }
    if (M.ENUMS[t] && t !== "led_anim" || t === "led_anim") {
      if (M.ENUMS[t]) {
        const val = String(action.value || action.button || M.ENUMS[t][0]);
        const opts = M.ENUMS[t].map((o) => ({ value: o, label: o.replace(/_/g, " ") }));
        return <Select className="grow" value={val} options={opts}
          onChange={(v) => set(t === "mouse_click" ? { button: v } : (t === "profile" ? { value: parseInt(v) } : { value: v }))} />;
      }
    }
    if (t === "mouse_move") {
      return (
        <div className="row grow" style={{ gap: 8 }}>
          <Field label=""><input className="input mono" type="number" style={{ width: 90 }} value={action.x || 0}
            onChange={(e) => set({ x: parseInt(e.target.value || "0") })} placeholder="x" /></Field>
          <Field label=""><input className="input mono" type="number" style={{ width: 90 }} value={action.y || 0}
            onChange={(e) => set({ y: parseInt(e.target.value || "0") })} placeholder="y" /></Field>
          <span className="faint fs12">pixels Δ</span>
        </div>
      );
    }
    if (t === "led") {
      const c = action.color || [255, 138, 76];
      return (
        <div className="col grow" style={{ gap: 10 }}>
          <div className="row wrap" style={{ gap: 6 }}>
            {SWATCHES.map((s, i) => {
              const on = s.join() === c.join();
              return <button key={i} onClick={() => set({ color: s })} title={rgbCss(s)}
                style={{ width: 26, height: 26, borderRadius: 8, background: rgbCss(s),
                  border: on ? "2px solid var(--text)" : "1px solid var(--line-strong)",
                  boxShadow: on ? `0 0 0 3px rgba(var(--accent-glow),0.3)` : "none", cursor: "pointer",
                  transition: "transform .25s var(--spring)" }}
                onMouseDown={(e) => e.currentTarget.style.transform = "scale(0.88)"}
                onMouseUp={(e) => e.currentTarget.style.transform = ""} />;
            })}
            <label className="chip" style={{ cursor: "pointer", height: 26 }}>
              <Icon name="eyedropper" w="bold" /> custom
              <input type="color" value={rgbToHex(c)} onChange={(e) => set({ color: hexToRgb(e.target.value) })}
                style={{ width: 0, height: 0, opacity: 0, position: "absolute" }} />
            </label>
            <span className="chip mono">{rgbCss(c)}</span>
          </div>
        </div>
      );
    }
    return <span className="faint fs12">No options</span>;
  }

  // ---- single action card ----
  function ActionCard({ action, index, total, running, onChange, onDelete, onMove, onDrag, dragState }) {
    const meta = M.ACTION_META[action.type];
    const [armed, setArmed] = useState(false);
    const isDragging = dragState.from === index;
    const isOver = dragState.over === index && dragState.from !== index;

    return (
      <div
        className={`action-card ${running ? "running" : ""} ${isDragging ? "dragging" : ""} ${isOver ? "drag-over" : ""}`}
        draggable={armed}
        onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; onDrag("start", index); }}
        onDragEnd={() => { onDrag("end"); setArmed(false); }}
        onDragOver={(e) => { e.preventDefault(); onDrag("over", index); }}
        onDrop={(e) => { e.preventDefault(); onDrag("drop", index); }}
      >
        <div className="ac-handle" onMouseDown={() => setArmed(true)} onMouseUp={() => setArmed(false)} title="Drag to reorder">
          <Icon name="dots-six-vertical" w="bold" />
        </div>
        <div className="ac-icon">
          <ActionTile type={action.type} />
        </div>
        <div className="ac-label">{meta.label}</div>
        <div className="ac-edit">
          <ValueEditor action={action} onChange={onChange} />
        </div>
        <div className="ac-actions">
          {index > 0 && <IconBtn icon="arrow-up" size="sm" title="Move up" onClick={() => onMove(index - 1)} />}
          {index < total - 1 && <IconBtn icon="arrow-down" size="sm" title="Move down" onClick={() => onMove(index + 1)} />}
          <IconBtn icon="trash" size="sm" title="Delete step" onClick={onDelete} />
        </div>
      </div>
    );
  }

  // ---- action picker popover ----
  function Picker({ onPick, onClose }) {
    useDismiss(true, onClose);
    return (
      <div className="picker" data-pop>
        {M.CATS.map((cat) => {
          const types = Object.keys(M.ACTION_META).filter((t) => M.ACTION_META[t].cat === cat);
          return (
            <div key={cat}>
              <div className="picker-cat">{cat}</div>
              {types.map((t) => {
                const m = M.ACTION_META[t];
                return (
                  <button key={t} className="picker-item" onClick={() => { onPick(t); onClose(); }}>
                    <ActionTile type={t} size={32} radius={9} font={16} />
                    <div className="col">
                      <span className="pi-t">{m.label}</span>
                      <span className="pi-d">{m.desc}</span>
                    </div>
                  </button>
                );
              })}
            </div>
          );
        })}
      </div>
    );
  }

  // syntax-highlighted JSON
  function jsonHtml(obj) {
    let s = JSON.stringify(obj, null, 2);
    s = s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
    s = s.replace(/"([^"]+)":/g, '<span class="k">"$1"</span>:');
    s = s.replace(/: "([^"]*)"/g, ': <span class="s">"$1"</span>');
    s = s.replace(/: (-?\d+)/g, ': <span class="n">$1</span>');
    return s;
  }

  // ---- main builder ----
  function ActionBuilder({ keyData, runningIndex, onRename, onChangeAction, onDeleteAction, onAddAction, onReorder, onTest, onAiGenerate, aiBusy, defaultAdvanced }) {
    const [pickerOpen, setPickerOpen] = useState(false);
    const [advanced, setAdvanced] = useState(!!defaultAdvanced);
    const [drag, setDrag] = useState({ from: null, over: null });
    const [aiOpen, setAiOpen] = useState(false);
    const [aiPrompt, setAiPrompt] = useState("");
    const actions = keyData.actions || [];

    useEffect(() => { setAdvanced(!!defaultAdvanced); }, [defaultAdvanced]);
    const runAi = () => { if (aiPrompt.trim()) { onAiGenerate(aiPrompt); setAiPrompt(""); } };

    const handleDrag = (phase, index) => {
      if (phase === "start") setDrag({ from: index, over: index });
      else if (phase === "over") setDrag((d) => (d.over === index ? d : { ...d, over: index }));
      else if (phase === "drop") { if (drag.from != null && drag.from !== index) onReorder(drag.from, index); setDrag({ from: null, over: null }); }
      else setDrag({ from: null, over: null });
    };

    return (
      <div className="view-enter" key={keyData.id}>
        <div className="builder-head">
          <div className="builder-key-badge">{keyData.id}</div>
          <div className="builder-title">
            <input value={keyData.name || ""} placeholder="Untitled key"
              onChange={(e) => onRename(e.target.value)} />
            <div className="sub">{actions.length} step{actions.length !== 1 ? "s" : ""} · runs top to bottom</div>
          </div>
          {onAiGenerate && <Btn icon="sparkle" onClick={() => setAiOpen((v) => !v)} style={aiOpen ? { color: "var(--accent)" } : null}>AI</Btn>}
          <Btn icon="play" variant="primary" onClick={onTest} disabled={!actions.length}>Test</Btn>
        </div>

        {aiOpen && onAiGenerate && (
          <div className="row" style={{ gap: 8, marginBottom: 16 }}>
            <input className="input grow" autoFocus placeholder="Describe this key in words — e.g. “open terminal and run npm test”"
              value={aiPrompt} onChange={(e) => setAiPrompt(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") runAi(); }} />
            <Btn variant="primary" icon="sparkle" disabled={aiBusy || !aiPrompt.trim()} onClick={runAi}>{aiBusy ? "Generating…" : "Generate"}</Btn>
          </div>
        )}

        <div className="timeline">
          {actions.length === 0 ? (
            <div className="empty-actions">
              <Icon name="stack-plus" w="bold" />
              <div className="fw600">No actions yet</div>
              <div className="fs13 faint mt8">Add a step below to start building this macro.</div>
            </div>
          ) : (
            actions.map((a, i) => (
              <ActionCard key={i} action={a} index={i} total={actions.length}
                running={runningIndex === i}
                onChange={(na) => onChangeAction(i, na)}
                onDelete={() => onDeleteAction(i)}
                onMove={(to) => onReorder(i, to)}
                onDrag={handleDrag} dragState={drag} />
            ))
          )}

          <div style={{ position: "relative" }}>
            <button className="add-action" onClick={() => setPickerOpen((v) => !v)} data-pop>
              <Icon name="plus" w="bold" /> Add action
            </button>
            {pickerOpen && (
              <div style={{ position: "absolute", top: "calc(100% + 6px)", left: 0 }}>
                <Picker onPick={(t) => onAddAction(makeAction(t))} onClose={() => setPickerOpen(false)} />
              </div>
            )}
          </div>
        </div>

        <div className="divider" />
        <button className={`adv-toggle ${advanced ? "open" : ""}`} onClick={() => setAdvanced((v) => !v)}>
          <Icon name="caret-right" w="bold" className="chev" />
          <Icon name="code" w="bold" /> Advanced — raw definition
        </button>
        <Collapse open={advanced}>
          <div className="adv-inner">
            <div className="hint"><Icon name="info" w="bold" /> This is the exact JSON written to the device for key {keyData.id}.</div>
            <div className="json-view" dangerouslySetInnerHTML={{ __html: jsonHtml({ id: keyData.id, name: keyData.name, actions }) }} />
          </div>
        </Collapse>
      </div>
    );
  }

  function makeAction(t) {
    switch (t) {
      case "text": return { type: "text", value: "" };
      case "keycombo": return { type: "keycombo", keys: [] };
      case "key": return { type: "key", value: "ENTER" };
      case "hold": return { type: "hold", key: "LEFT_SHIFT" };
      case "release": return { type: "release", value: "LEFT_SHIFT" };
      case "delay": return { type: "delay", ms: 100 };
      case "media": return { type: "media", value: "PLAY_PAUSE" };
      case "telephony": return { type: "telephony", value: "MIC_MUTE" };
      case "mouse_click": return { type: "mouse_click", button: "LEFT" };
      case "mouse_move": return { type: "mouse_move", x: 0, y: 0 };
      case "profile": return { type: "profile", value: 1 };
      case "led": return { type: "led", color: [255, 138, 76] };
      case "led_anim": return { type: "led_anim", value: "breathe" };
      default: return { type: t };
    }
  }

  window.ActionBuilder = ActionBuilder;
})();
