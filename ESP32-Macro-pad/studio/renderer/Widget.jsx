/* ============================================================
   MACROPAD STUDIO — Floating AI widget
   ============================================================ */
(function () {
  const { useState, useRef, useEffect } = React;
  const { Icon, IconBtn, rgbCss } = window.UI;
  const M = window.MACRO;

  function Widget({ ctxId, alpha, onClose, onRegen, recsFor, onPush }) {
    const ctx = M.CONTEXTS.find((c) => c.id === ctxId) || M.CONTEXTS[0];
    const recs = (recsFor ? recsFor(ctx.id) : ctx.recs) || [];
    // null until measured after mount, so we anchor against the real viewport
    // (not a transiently-small initial layout pass) and re-anchor on resize
    // until the user drags the widget.
    const [pos, setPos] = useState(null);
    const [spinning, setSpinning] = useState(null);
    const [idx, setIdx] = useState({});
    const drag = useRef(null);
    const moved = useRef(false);
    const elRef = useRef(null);

    useEffect(() => {
      const anchor = () => {
        if (moved.current) return;
        const w = elRef.current ? elRef.current.offsetWidth : 320;
        const h = elRef.current ? elRef.current.offsetHeight : 280;
        setPos({
          x: Math.max(16, window.innerWidth - w - 28),
          y: Math.max(80, window.innerHeight - h - 28),
        });
      };
      anchor();
      window.addEventListener("resize", anchor);
      return () => window.removeEventListener("resize", anchor);
    }, []);

    const onDown = (e) => {
      moved.current = true;
      drag.current = { sx: e.clientX, sy: e.clientY, ox: pos.x, oy: pos.y };
      const move = (ev) => {
        const d = drag.current; if (!d) return;
        setPos({
          x: Math.max(8, Math.min(window.innerWidth - 320, d.ox + ev.clientX - d.sx)),
          y: Math.max(8, Math.min(window.innerHeight - 120, d.oy + ev.clientY - d.sy)),
        });
      };
      const up = () => { drag.current = null; window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
    };

    const regen = (kn) => {
      setSpinning(kn);
      onRegen && onRegen(ctx.id, kn);
      setTimeout(() => setSpinning(null), 1100);
    };

    return (
      <div className="widget" ref={elRef}
        style={{ left: pos ? pos.x : -9999, top: pos ? pos.y : -9999, opacity: pos ? alpha : 0 }}>
        <div className="widget-bar" onMouseDown={onDown}>
          <span className="dot" />
          <span className="title">{ctx.label}</span>
          <IconBtn icon="arrow-clockwise" size="sm" w="bold" title="Regenerate all" onClick={() => regen("all")}
            className={spinning === "all" ? "" : ""} />
          <IconBtn icon="x" size="sm" w="bold" title="Hide" onClick={onClose} />
        </div>
        <div className="widget-body">
          {recs.map((r) => {
            const isSpin = spinning === r.key_num || spinning === "all";
            const led = M.ledColorOf({ actions: r.actions }) || [255, 138, 76];
            return (
              <div className="wkey" key={r.key_num} style={{ borderLeftColor: rgbCss(led) }}>
                <span className="wk-chip">K{r.key_num}</span>
                <div className="wk-text">
                  <div className="wk-desc">{r.description}</div>
                  <div className="wk-macro">{r.actions.map((a) => M.summarize(a)).join("  →  ")}</div>
                </div>
                <div className="wk-ctrl">
                  <IconBtn icon="arrow-clockwise" size="sm" title="Regenerate"
                    className={isSpin ? "spin" : ""} onClick={() => regen(r.key_num)} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  window.Widget = Widget;
})();
