/* VacancyRadar web UI - QWebChannel bridge */
(function () {
  const state = {
    page: "queue",
    items: [],
    selectedUrl: "",
    detail: null,
    stats: {},
    counts: { total: 0, new: 0, applied: 0 },
    settings: {},
    logs: [],
    hotkey: "Ctrl + Alt + Q",
    hkStatus: "",
    busy: { search: false, stats: false },
  };

  let bridge = null;

  function send(action, payload) {
    if (!bridge) return;
    bridge.call(action, JSON.stringify(payload || {}));
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function iconSvg(kind) {
    if (kind === "invite" || kind === "interview" || kind === "chat") {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 18l6-6-6-6M8 6l-6 6 6 6"/></svg>';
    }
    if (kind === "apply") {
      return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 21V7l9-4 9 4v14"/><path d="M9 21V12h6v9"/></svg>';
    }
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/></svg>';
  }

  function pillClass(kind) {
    if (kind === "pointer") return "pill-now";
    if (kind === "invite") return "pill-invite";
    if (kind === "apply") return "pill-applied";
    return "pill-new";
  }

  function statusClass(kind) {
    if (kind === "pointer") return "is-pointer";
    if (kind === "invite") return "is-invite";
    if (kind === "apply") return "is-apply";
    return "is-new";
  }

  function showPage(name) {
    state.page = name;
    document.querySelectorAll(".page-panel").forEach((el) => {
      el.hidden = el.id !== "page-" + name;
      if (el.id === "page-queue") el.style.display = name === "queue" ? "" : "none";
    });
    const q = document.getElementById("page-queue");
    if (q) q.style.display = name === "queue" ? "grid" : "none";
    document.querySelectorAll(".nav a").forEach((a) => {
      a.classList.toggle("active", a.dataset.page === name);
    });
  }

  function renderList() {
    const ul = document.getElementById("vac-list");
    if (!ul) return;
    const rows = state.items
      .map((it) => {
        const active = it.url === state.selectedUrl || it.kind === "pointer";
        const kind = active && it.kind !== "pointer" ? it.kind : it.kind;
        const cls = ["vac-item", statusClass(it.kind)];
        if (it.url === state.selectedUrl) cls.push("active");
        if (it.kind === "pointer") cls.push("is-pointer");
        const title = esc(it.title || "");
        return (
          '<li><button class="' +
          cls.join(" ") +
          '" type="button" data-url="' +
          esc(it.url) +
          '">' +
          '<span class="vac-stripe" aria-hidden="true"></span>' +
          '<span class="vac-icon" aria-hidden="true">' +
          iconSvg(it.kind) +
          "</span>" +
          '<span class="vac-body">' +
          '<div class="vac-title">' +
          title +
          "</div>" +
          '<div class="vac-company">' +
          esc(it.company || "") +
          "</div>" +
          '<div class="vac-meta">' +
          esc(it.meta || "") +
          "</div>" +
          "</span>" +
          '<span class="pill ' +
          pillClass(it.kind) +
          '">' +
          esc(it.pill || "") +
          "</span>" +
          '<span class="vac-score">' +
          (it.score > 0 ? it.score : "") +
          "</span>" +
          "</button></li>"
        );
      })
      .join("");
    ul.innerHTML = rows;
    ul.querySelectorAll(".vac-item").forEach((btn) => {
      btn.addEventListener("click", () => send("select", { url: btn.dataset.url }));
    });
    document.getElementById("vac-count").textContent =
      "Vacancies (" + (state.counts.total || state.items.length || 0) + ")";
  }

  function renderDetail() {
    const d = state.detail;
    if (!d) {
      document.getElementById("d-title").textContent = "Select a vacancy";
      document.getElementById("d-company").textContent = "";
      document.getElementById("d-meta").innerHTML = "";
      document.getElementById("d-score").innerHTML = "-";
      document.getElementById("d-facts").innerHTML = "";
      document.getElementById("d-skills").innerHTML = "";
      document.getElementById("d-letter").textContent = "";
      return;
    }
    document.getElementById("d-title").textContent = d.title || "";
    document.getElementById("d-company").innerHTML =
      esc(d.company || "") +
      ' <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="13" height="13"><path d="M14 4h6v6"/><path d="M10 14L20 4"/><path d="M20 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1h5"/></svg>';
    const meta = (d.meta || []).map(esc).join(' <span class="dot"></span> ');
    document.getElementById("d-meta").innerHTML = meta;
    const sc = d.score || 0;
    document.getElementById("d-score").innerHTML = sc
      ? sc + ' <span>/ 100</span>'
      : "-";
    const facts = d.facts || [];
    document.getElementById("d-facts").innerHTML = facts
      .map(
        (f) =>
          '<div class="facts-row"><dt>' +
          esc(f.label) +
          "</dt><dd>" +
          esc(f.value) +
          "</dd></div>"
      )
      .join("");
    const skills = d.skills || [];
    document.getElementById("d-skills").innerHTML = skills
      .map((s) => '<span class="skill">' + esc(s) + "</span>")
      .join("");
    document.getElementById("d-letter").textContent = d.letter || "";
  }

  function renderStrip() {
    const c = state.counts || {};
    const st = state.stats || {};
    const cells = [
      { label: "Total", value: c.total != null ? c.total : "-", tone: "teal", icon: "bag" },
      { label: "New", value: c.new != null ? c.new : "-", tone: "green", icon: "ok" },
      { label: "Applied", value: c.applied != null ? c.applied : "-", tone: "gray", icon: "check" },
      {
        label: "Employer Replies",
        value: st.invitations != null ? st.invitations : "-",
        tone: "blue",
        icon: "users",
      },
      {
        label: "Interviews",
        value: st.interviews != null ? st.interviews : "-",
        tone: "purple",
        icon: "clip",
      },
      {
        label: "Offers",
        value: st.unread_messages != null ? st.unread_messages : "-",
        tone: "gold",
        icon: "gift",
      },
    ];
    const icons = {
      bag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><rect x="3" y="7" width="18" height="14" rx="2"/></svg>',
      ok: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>',
      check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>',
      users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="3"/></svg>',
      clip: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 6h8v4H8z"/><path d="M6 10h12v10H6z"/></svg>',
      gift: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 12v8H4v-8"/><path d="M2 7h20v5H2z"/></svg>',
    };
    document.getElementById("strip-stats").innerHTML = cells
      .map(
        (c) =>
          '<div class="stat"><div class="stat-icon ' +
          c.tone +
          '">' +
          icons[c.icon] +
          '</div><div class="stat-text"><div class="label">' +
          c.label +
          '</div><div class="value">' +
          esc(c.value) +
          "</div></div></div>"
      )
      .join("");
    document.getElementById("strip-updated").textContent =
      "Last Updated: " + (st.updated_at || "-");
  }

  function renderStatsPage() {
    const st = state.stats || {};
    const cards = [
      ["Waiting", st.active_responses],
      ["Total responses", st.total_responses],
      ["Invitations", st.invitations],
      ["Interviews", st.interviews],
      ["Refusals", st.refusals],
      ["Unread chats", st.unread_messages],
      ["Resume views", st.resume_views],
      ["Resume shows", st.resume_shows],
    ];
    document.getElementById("stats-cards").innerHTML = cards
      .map(
        ([label, val]) =>
          '<div class="metric-card"><div class="mc-top"><span class="mc-label">' +
          esc(label) +
          '</span></div><div class="mc-value">' +
          esc(val == null ? "-" : val) +
          "</div></div>"
      )
      .join("");
    const grid = [
      ["Queue (new)", state.counts.new],
      ["Applied (waiting)", state.counts.applied],
      ["Note", st.note || ""],
    ];
    document.getElementById("stats-grid").innerHTML = grid
      .map(
        ([k, v]) =>
          "<label>" + esc(k) + '</label><div class="value">' + esc(v == null ? "-" : v) + "</div>"
      )
      .join("");
  }

  function renderSettings() {
    const s = state.settings || {};
    document.getElementById("opt-sound").checked = !!s.sound_enabled;
    document.getElementById("opt-dnd").checked = !!s.dnd;
    document.getElementById("opt-min").checked = !!s.minimize_previous;
    document.getElementById("opt-autostart").checked = !!s.autostart_enabled;
    const scoring = document.getElementById("opt-scoring");
    if (scoring) scoring.value = s.scoring_mode === "rules" ? "rules" : "cursor";
    const sel = document.getElementById("opt-theme");
    if (sel && s.themes && !sel.dataset.filled) {
      sel.innerHTML = (s.themes || [])
        .map(
          (t) =>
            '<option value="' +
            esc(t.id) +
            '"' +
            (t.id === s.ui_theme ? " selected" : "") +
            ">" +
            esc(t.label) +
            "</option>"
        )
        .join("");
      sel.dataset.filled = "1";
    } else if (sel && s.ui_theme) {
      sel.value = s.ui_theme;
    }
    document.getElementById("hotkey-badge").textContent = state.hotkey;
    document.getElementById("hotkey-badge-2").textContent = state.hotkey;
    document.getElementById("hk-status").textContent = state.hkStatus || "";
    document.getElementById("log-box").textContent = (state.logs || []).slice(-80).join("\n");
  }

  function renderBusy() {
    document.getElementById("btn-search").disabled = !!state.busy.search;
    document.getElementById("btn-stats").disabled = !!state.busy.stats;
    const b2 = document.getElementById("btn-stats2");
    if (b2) b2.disabled = !!state.busy.stats;
  }

  function renderAll() {
    renderList();
    renderDetail();
    renderStrip();
    renderStatsPage();
    renderSettings();
    renderBusy();
  }

  window.RadarUI = {
    onEvent: function (event, data) {
      data = data || {};
      if (event === "queue") {
        state.items = data.items || [];
        state.counts = data.counts || state.counts;
        if (data.selectedUrl) state.selectedUrl = data.selectedUrl;
        renderList();
        renderStrip();
      } else if (event === "detail") {
        state.detail = data;
        state.selectedUrl = data.url || state.selectedUrl;
        renderDetail();
        renderList();
      } else if (event === "stats") {
        state.stats = data.stats || data;
        if (data.counts) state.counts = Object.assign({}, state.counts, data.counts);
        renderStrip();
        renderStatsPage();
      } else if (event === "settings") {
        state.settings = data;
        renderSettings();
      } else if (event === "log") {
        if (data.line) state.logs.push(data.line);
        if (data.lines) state.logs = data.lines;
        renderSettings();
      } else if (event === "hotkey") {
        if (data.label) state.hotkey = data.label;
        if (data.status != null) state.hkStatus = data.status;
        renderSettings();
      } else if (event === "busy") {
        state.busy = Object.assign({}, state.busy, data);
        renderBusy();
      } else if (event === "page") {
        showPage(data.name || "queue");
      }
    },
  };

  function wire() {
    document.getElementById("btn-search").onclick = () => send("search");
    document.getElementById("btn-stats").onclick = () => send("stats");
    document.getElementById("btn-stats2").onclick = () => send("stats");
    document.getElementById("btn-open").onclick = () => send("open");
    document.getElementById("btn-view").onclick = () => send("open");
    document.getElementById("btn-applied").onclick = () => send("mark", { status: "applied" });
    document.getElementById("btn-skip").onclick = () => send("mark", { status: "skipped" });
    document.getElementById("btn-ban").onclick = () => send("mark", { status: "banned" });
    document.getElementById("btn-copy").onclick = () => send("copyLetter");
    document.getElementById("btn-login").onclick = () => send("login");
    document.getElementById("btn-check").onclick = () => send("check");
    document.getElementById("btn-letters").onclick = () => send("rebuildLetters");
    document.getElementById("btn-hk-assign").onclick = () => send("captureHotkey");
    document.getElementById("btn-hk-test").onclick = () => send("testHotkey");
    document.getElementById("btn-hk-reset").onclick = () => send("resetHotkey");
    document.querySelectorAll(".nav a").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        showPage(a.dataset.page);
        send("page", { name: a.dataset.page });
      });
    });
    document.querySelectorAll("[data-guide]").forEach((b) => {
      b.onclick = () => send("guide", { name: b.dataset.guide });
    });
    ["opt-sound", "opt-dnd", "opt-min", "opt-autostart"].forEach((id) => {
      const el = document.getElementById(id);
      el.addEventListener("change", () => {
        send("setOpt", {
          sound_enabled: document.getElementById("opt-sound").checked,
          dnd: document.getElementById("opt-dnd").checked,
          minimize_previous: document.getElementById("opt-min").checked,
          autostart_enabled: document.getElementById("opt-autostart").checked,
          scoring_mode: document.getElementById("opt-scoring").value,
        });
      });
    });
    document.getElementById("opt-scoring").addEventListener("change", () => {
      send("setOpt", {
        sound_enabled: document.getElementById("opt-sound").checked,
        dnd: document.getElementById("opt-dnd").checked,
        minimize_previous: document.getElementById("opt-min").checked,
        autostart_enabled: document.getElementById("opt-autostart").checked,
        scoring_mode: document.getElementById("opt-scoring").value,
      });
    });
    document.getElementById("opt-theme").addEventListener("change", (e) => {
      send("setTheme", { id: e.target.value });
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "F5") {
        e.preventDefault();
        send("search");
      }
      if (e.key === "F9") {
        e.preventDefault();
        send("stats");
      }
    });
  }

  function connect() {
    if (typeof qt === "undefined" || !qt.webChannelTransport) {
      wire();
      renderAll();
      return;
    }
    new QWebChannel(qt.webChannelTransport, function (channel) {
      bridge = channel.objects.radar;
      wire();
      renderAll();
      send("ready", {});
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", connect);
  } else {
    connect();
  }
})();
