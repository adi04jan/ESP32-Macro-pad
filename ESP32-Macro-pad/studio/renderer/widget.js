/* Always-on-top overlay: a minimal spatial grid mirroring the physical macropad
 * so you can glance at key positions. Each tile shows the key number, an LED-
 * colour dot, and the key name (full name on hover). Flashes on press. */
(function () {
  const M = window.MACRO || {};
  const LAYOUT = M.LAYOUT || [[null, 1, 2, null], [3, 4, 5, 6], [7, 8, 9, 10], [null, 11, 12, null]];
  const gridEl = document.getElementById("grid");
  const pnameEl = document.getElementById("pname");
  const cellsById = {};

  function rgb(c) { return Array.isArray(c) ? `rgb(${c[0]},${c[1]},${c[2]})` : ""; }
  function summarize(actions) {
    if (!actions || !actions.length) return "unassigned";
    return actions.map((a) => (M.summarize ? M.summarize(a) : a.type)).join("  →  ");
  }

  function render(profile) {
    profile = profile || { keys: [] };
    pnameEl.textContent = profile.profile_name || "—";
    const byId = {};
    (profile.keys || []).forEach((k) => (byId[k.id] = k));
    gridEl.innerHTML = "";
    for (const id in cellsById) delete cellsById[id];

    LAYOUT.flat().forEach((id) => {
      if (id == null) { const e = document.createElement("div"); e.className = "cell empty"; gridEl.appendChild(e); return; }
      const k = byId[id] || { id };
      const has = k.actions && k.actions.length;
      const led = M.ledColorOf ? M.ledColorOf(k) : (k.glow || null);

      const cell = document.createElement("div");
      cell.className = "cell" + (has ? "" : " unmapped");
      cell.title = has ? `K${id} · ${summarize(k.actions)}` : `K${id} · unassigned`;

      const top = document.createElement("div");
      top.className = "top";
      const n = document.createElement("span"); n.className = "n"; n.textContent = id;
      const dot = document.createElement("span"); dot.className = "led";
      if (led) { dot.style.background = rgb(led); dot.style.boxShadow = `0 0 5px ${rgb(led)}`; }
      top.appendChild(n); top.appendChild(dot);

      const nm = document.createElement("div");
      nm.className = "nm";
      nm.textContent = k.name || (has ? "Key " + id : "—");

      const dt = document.createElement("div");
      dt.className = "dt";
      dt.textContent = has ? summarize(k.actions) : "unassigned";

      cell.appendChild(top); cell.appendChild(nm); cell.appendChild(dt);
      gridEl.appendChild(cell);
      cellsById[id] = cell;
    });
  }

  function flash(id) {
    const cell = cellsById[id];
    if (!cell) return;
    cell.classList.add("flash");
    clearTimeout(cell._t);
    cell._t = setTimeout(() => cell.classList.remove("flash"), 300);
  }

  if (window.widgetApi) {
    window.widgetApi.onData(render);
    window.widgetApi.onKey((d) => { if (d && d.down) flash(d.key | 0); });
    document.getElementById("close").addEventListener("click", () => window.widgetApi.close());
    window.widgetApi.ready();
  }
  render(null);
})();
