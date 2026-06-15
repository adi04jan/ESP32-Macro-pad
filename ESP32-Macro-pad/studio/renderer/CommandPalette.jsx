/* ============================================================
   MACROPAD STUDIO — Command palette (⌘K)
   ============================================================ */
(function () {
  const { useState, useEffect, useRef } = React;
  const { Icon } = window.UI;
  const M = window.MACRO;

  function CommandPalette({ onClose, onRun }) {
    const [q, setQ] = useState("");
    const [sel, setSel] = useState(0);
    const inputRef = useRef(null);

    const commands = [
      { cat: "Navigate", icon: "squares-four", t: "Go to Key Editor", h: "1", run: () => onRun("nav", "editor") },
      { cat: "Navigate", icon: "gauge", t: "Go to Dashboard", h: "2", run: () => onRun("nav", "dashboard") },
      { cat: "Navigate", icon: "binoculars", t: "Go to Auto-Switcher", h: "3", run: () => onRun("nav", "auto") },
      { cat: "Navigate", icon: "gear-six", t: "Go to Settings", h: "4", run: () => onRun("nav", "settings") },
      { cat: "Action", icon: "moon-stars", t: "Toggle theme", h: "T", run: () => onRun("theme") },
      { cat: "Action", icon: "app-window", t: "Toggle floating widget", h: "W", run: () => onRun("widget") },
      { cat: "Action", icon: "code", t: "Toggle advanced mode", h: "", run: () => onRun("advanced") },
      { cat: "Action", icon: "plugs-connected", t: "Connect / disconnect device", h: "", run: () => onRun("connect") },
      { cat: "Action", icon: "play", t: "Test current key", h: "", run: () => onRun("test") },
      ...M.SEED.keys.map((k) => ({ cat: "Jump to key", icon: "keyboard", t: `Key ${k.id} — ${k.name}`, h: "K" + k.id, run: () => onRun("key", k.id) })),
    ];

    const filtered = q ? commands.filter((c) => (c.t + c.cat).toLowerCase().includes(q.toLowerCase())) : commands;

    useEffect(() => { inputRef.current && inputRef.current.focus(); }, []);
    useEffect(() => { setSel(0); }, [q]);
    useEffect(() => {
      const onKey = (e) => {
        if (e.key === "Escape") onClose();
        else if (e.key === "ArrowDown") { e.preventDefault(); setSel((s) => Math.min(filtered.length - 1, s + 1)); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setSel((s) => Math.max(0, s - 1)); }
        else if (e.key === "Enter") { e.preventDefault(); filtered[sel] && (filtered[sel].run(), onClose()); }
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [filtered, sel]);

    let lastCat = null;
    return (
      <div className="cmdk-overlay" onMouseDown={onClose}>
        <div className="cmdk" onMouseDown={(e) => e.stopPropagation()}>
          <div className="cmdk-input">
            <Icon name="magnifying-glass" w="bold" />
            <input ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type a command or search keys…" />
            <span className="kbd">esc</span>
          </div>
          <div className="cmdk-list">
            {filtered.length === 0 && <div className="faint" style={{ padding: 24, textAlign: "center" }}>No matches</div>}
            {filtered.map((c, i) => {
              const showCat = c.cat !== lastCat; lastCat = c.cat;
              return (
                <React.Fragment key={i}>
                  {showCat && <div className="cmdk-cat">{c.cat}</div>}
                  <div className={`cmdk-item ${i === sel ? "sel" : ""}`} onMouseEnter={() => setSel(i)}
                    onClick={() => { c.run(); onClose(); }}>
                    <span className="ci-ic"><Icon name={c.icon} w="bold" /></span>
                    <span className="ci-t">{c.t}</span>
                    {c.h && <span className="kbd">{c.h}</span>}
                  </div>
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  window.CommandPalette = CommandPalette;
})();
