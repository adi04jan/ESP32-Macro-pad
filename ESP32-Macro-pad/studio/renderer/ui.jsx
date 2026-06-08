/* ============================================================
   MACROPAD STUDIO — shared UI primitives
   ============================================================ */
(function () {
  const { useState, useRef, useEffect, useLayoutEffect } = React;

  const Icon = ({ name, w, className = "", style, onClick }) =>
    React.createElement("i", {
      className: `ph${w ? "-" + w : ""} ph-${name} ${className}`,
      style, onClick,
    });

  function Btn({ children, icon, variant = "", size = "", className = "", ...rest }) {
    const v = variant ? `btn-${variant}` : "";
    const s = size ? size : "";
    return (
      <button className={`btn ${v} ${s} ${className}`} {...rest}>
        {icon && <Icon name={icon} w="bold" />}
        {children}
      </button>
    );
  }

  function IconBtn({ icon, w = "regular", size = "", className = "", title, ...rest }) {
    return (
      <button className={`icon-btn ${size} ${className}`} title={title} {...rest}>
        <Icon name={icon} w={w} />
      </button>
    );
  }

  function Toggle({ on, onChange }) {
    return <button className={`toggle ${on ? "on" : ""}`} onClick={() => onChange(!on)} aria-pressed={on} />;
  }

  // Segmented control with sliding thumb
  function Segmented({ options, value, onChange, className = "" }) {
    const ref = useRef(null);
    const [thumb, setThumb] = useState({ left: 3, width: 0 });
    useLayoutEffect(() => {
      const root = ref.current; if (!root) return;
      const active = root.querySelector(".seg-opt.active");
      if (active) setThumb({ left: active.offsetLeft, width: active.offsetWidth });
    }, [value, options]);
    return (
      <div className={`seg ${className}`} ref={ref}>
        <div className="seg-thumb" style={{ transform: `translateX(${thumb.left - 3}px)`, width: thumb.width }} />
        {options.map((o) => {
          const val = typeof o === "string" ? o : o.value;
          const label = typeof o === "string" ? o : o.label;
          const ic = typeof o === "string" ? null : o.icon;
          return (
            <button key={val} className={`seg-opt ${value === val ? "active" : ""}`} onClick={() => onChange(val)}>
              {ic && <Icon name={ic} w="bold" />}{label}
            </button>
          );
        })}
      </div>
    );
  }

  function Select({ value, onChange, options, className = "" }) {
    return (
      <div className={`select-wrap ${className}`}>
        <select className="select" value={value} onChange={(e) => onChange(e.target.value)}>
          {options.map((o) => {
            const val = typeof o === "object" ? o.value : o;
            const label = typeof o === "object" ? o.label : o;
            return <option key={val} value={val}>{label}</option>;
          })}
        </select>
        <Icon name="caret-down" w="bold" />
      </div>
    );
  }

  function Field({ label, children }) {
    return (
      <label className="field">
        {label && <span className="field-label">{label}</span>}
        {children}
      </label>
    );
  }

  function Panel({ title, sub, icon, right, children, className = "", bodyClass = "panel-pad" }) {
    return (
      <section className={`panel ${className}`}>
        {(title || right) && (
          <div className="panel-head">
            {icon && <Icon name={icon} w="bold" style={{ fontSize: 18, color: "var(--accent)" }} />}
            <div className="grow">
              {title && <h3>{title}</h3>}
              {sub && <div className="sub">{sub}</div>}
            </div>
            {right}
          </div>
        )}
        <div className={bodyClass}>{children}</div>
      </section>
    );
  }

  // Smooth height auto-animate container
  function Collapse({ open, children }) {
    const ref = useRef(null);
    const [h, setH] = useState(open ? "auto" : 0);
    useEffect(() => {
      const el = ref.current; if (!el) return;
      if (open) {
        const target = el.scrollHeight;
        setH(target);
        const t = setTimeout(() => setH("auto"), 420);
        return () => clearTimeout(t);
      } else {
        setH(el.scrollHeight);
        requestAnimationFrame(() => requestAnimationFrame(() => setH(0)));
      }
    }, [open, children]);
    return (
      <div className="adv-panel" style={{ height: h === "auto" ? "auto" : h + "px" }}>
        <div ref={ref}>{children}</div>
      </div>
    );
  }

  // Lightweight popover that closes on outside click / escape
  function useDismiss(open, close) {
    useEffect(() => {
      if (!open) return;
      const onKey = (e) => { if (e.key === "Escape") close(); };
      const onClick = (e) => { if (!e.target.closest("[data-pop]")) close(); };
      window.addEventListener("keydown", onKey);
      window.addEventListener("mousedown", onClick);
      return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("mousedown", onClick); };
    }, [open]);
  }

  // colored icon tile used in action cards / pickers
  function ActionTile({ type, size = 38, radius = 11, font = 18 }) {
    const meta = window.MACRO.ACTION_META[type];
    if (!meta) return null;
    return (
      <div style={{
        width: size, height: size, borderRadius: radius,
        display: "grid", placeItems: "center",
        background: `color-mix(in oklch, ${meta.color} 18%, transparent)`,
        color: meta.color, fontSize: font,
      }}>
        <Icon name={meta.icon.replace("ph-", "")} w="bold" />
      </div>
    );
  }

  function rgbCss(c) { return c ? `rgb(${c[0]},${c[1]},${c[2]})` : "transparent"; }

  window.UI = { Icon, Btn, IconBtn, Toggle, Segmented, Select, Field, Panel, Collapse, useDismiss, ActionTile, rgbCss };
})();
