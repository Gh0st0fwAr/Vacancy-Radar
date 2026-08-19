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
    scoring: {
      profileSynced: false,
      preferencesSynced: false,
      referencesSynced: false,
      preferencesUnlocked: false,
      profileReady: false,
      filename: "",
      portfolio: "",
      github: "",
      activitySphere: "",
      preferences: { desirable: [], neutral: [], undesirable: [], reject: [] },
      refUrls: [],
      packNames: [],
      pendingFile: null,
      pendingFileName: "",
      dirtyProfile: false,
      dirtyPrefs: false,
      dirtyRefs: false,
    },
  };

  let bridge = null;
  let clearCheckDaysTimer = null;
  const uploadStatusTimers = {};
  const PREF_BUCKETS = ["desirable", "neutral", "undesirable", "reject"];
  const SCORING_STATUS_IDS = {
    profile: "up-profile-status",
    preferences: "up-pref-status",
    references: "up-ref-status",
  };

  function send(action, payload) {
    if (!bridge) return;
    bridge.call(action, JSON.stringify(payload || {}));
  }

  function setUploadStatus(elId, mode) {
    const el = document.getElementById(elId);
    if (!el) return;
    if (uploadStatusTimers[elId]) {
      clearTimeout(uploadStatusTimers[elId]);
      uploadStatusTimers[elId] = null;
    }
    if (mode === "loading") {
      el.innerHTML = '<span class="spin"></span> Analyzing…';
    } else if (mode === "ok") {
      el.innerHTML = '<span class="ok-check">✓</span> Saved';
      uploadStatusTimers[elId] = setTimeout(function () {
        el.innerHTML = "";
        uploadStatusTimers[elId] = null;
      }, 5000);
    } else if (mode === "error") {
      el.innerHTML = '<span style="color:var(--danger)">Error</span>';
      uploadStatusTimers[elId] = setTimeout(function () {
        el.innerHTML = "";
        uploadStatusTimers[elId] = null;
      }, 5000);
    } else {
      el.innerHTML = "";
    }
  }

  function scoringStatusEl(panel) {
    return SCORING_STATUS_IDS[panel] || "";
  }

  function readFileAsDataURL(file) {
    return new Promise(function (resolve, reject) {
      const fr = new FileReader();
      fr.onload = function () {
        resolve(fr.result);
      };
      fr.onerror = function () {
        reject(fr.error);
      };
      fr.readAsDataURL(file);
    });
  }

  function updateScoringPanelVisuals() {
    const sc = state.scoring;
    const pp = document.getElementById("panel-user-profile");
    const pref = document.getElementById("panel-preferences");
    const ref = document.getElementById("panel-references");
    if (pp) pp.classList.toggle("is-synced", sc.profileSynced && !sc.dirtyProfile);
    if (pref) {
      pref.classList.toggle("is-synced", sc.preferencesSynced && !sc.dirtyPrefs);
      // Stay unlocked after first successful profile Upload; dirty links must not lock prefs.
      pref.classList.toggle("is-disabled", !sc.preferencesUnlocked);
    }
    if (ref) ref.classList.toggle("is-synced", sc.referencesSynced && !sc.dirtyRefs);
  }

  function updateRefsUploadButton() {
    const btn = document.getElementById("btn-up-references");
    if (!btn) return;
    btn.disabled = collectRefUrls().length === 0;
  }

  function updateScoringControls() {
    const sc = state.scoring;
    const canEdit = sc.profileReady || !!sc.pendingFile;
    const port = document.getElementById("up-portfolio");
    const gh = document.getElementById("up-github");
    const sph = document.getElementById("up-sphere");
    const btnProf = document.getElementById("btn-up-profile");
    if (port) port.disabled = !canEdit;
    if (gh) gh.disabled = !canEdit;
    if (sph) sph.disabled = !canEdit;
    if (btnProf) btnProf.disabled = !canEdit;
    updateRefsUploadButton();
  }

  function markProfileDirty() {
    state.scoring.profileSynced = false;
    state.scoring.dirtyProfile = true;
    updateScoringPanelVisuals();
  }

  function markPrefsDirty() {
    state.scoring.preferencesSynced = false;
    state.scoring.dirtyPrefs = true;
    updateScoringPanelVisuals();
  }

  function markRefsDirty() {
    state.scoring.referencesSynced = false;
    state.scoring.dirtyRefs = true;
    updateScoringPanelVisuals();
  }

  function renderPrefTags(bucket) {
    const container = document.getElementById("pref-tags-" + bucket);
    if (!container) return;
    const tags = state.scoring.preferences[bucket] || [];
    container.innerHTML = tags
      .map(function (t, i) {
        return (
          '<span class="pref-tag">' +
          esc(t) +
          '<button type="button" class="x" data-bucket="' +
          esc(bucket) +
          '" data-idx="' +
          i +
          '" aria-label="Remove">×</button></span>'
        );
      })
      .join("");
    container.querySelectorAll(".x").forEach(function (btn) {
      btn.addEventListener("click", function () {
        removePrefTag(btn.dataset.bucket, parseInt(btn.dataset.idx, 10));
      });
    });
  }

  function addPrefTag(bucket, text) {
    text = String(text || "")
      .trim()
      .replace(/,+$/, "")
      .trim();
    if (!text) return;
    if (!state.scoring.preferences[bucket]) state.scoring.preferences[bucket] = [];
    const arr = state.scoring.preferences[bucket];
    if (arr.indexOf(text) >= 0) return;
    arr.push(text);
    markPrefsDirty();
    renderPrefTags(bucket);
  }

  function removePrefTag(bucket, idx) {
    const arr = state.scoring.preferences[bucket];
    if (!arr || idx < 0 || idx >= arr.length) return;
    arr.splice(idx, 1);
    markPrefsDirty();
    renderPrefTags(bucket);
  }

  function collectPreferencesFromDOM() {
    const p = state.scoring.preferences;
    return {
      desirable: (p.desirable || []).slice(),
      neutral: (p.neutral || []).slice(),
      undesirable: (p.undesirable || []).slice(),
      reject: (p.reject || []).slice(),
    };
  }

  function collectRefUrls() {
    const list = document.getElementById("ref-list");
    if (!list) return [];
    return Array.from(list.querySelectorAll(".ref-row input"))
      .map(function (inp) {
        return inp.value.trim();
      })
      .filter(Boolean);
  }

  function wireRefRows() {
    const list = document.getElementById("ref-list");
    if (!list) return;
    list.querySelectorAll(".ref-row").forEach(function (row) {
      const input = row.querySelector("input");
      const xBtn = row.querySelector(".x-row");
      if (input) {
        input.oninput = function () {
          markRefsDirty();
          updateRefsUploadButton();
        };
      }
      if (xBtn) {
        xBtn.onclick = function () {
          const rows = list.querySelectorAll(".ref-row");
          if (rows.length <= 1) {
            if (input) input.value = "";
            markRefsDirty();
            updateRefsUploadButton();
            return;
          }
          row.remove();
          markRefsDirty();
          updateRefsUploadButton();
        };
      }
    });
    updateRefsUploadButton();
  }

  function renderRefRows(urls) {
    const list = document.getElementById("ref-list");
    if (!list) return;
    const arr = urls && urls.length ? urls.slice() : [""];
    list.innerHTML = arr
      .map(function (url) {
        return (
          '<div class="ref-row">' +
          '<input class="input" type="url" placeholder="https://…" value="' +
          esc(url) +
          '" />' +
          '<button class="x-row" type="button" aria-label="Remove reference">×</button>' +
          "</div>"
        );
      })
      .join("");
    wireRefRows();
  }

  function renderPackSelect(names) {
    const sel = document.getElementById("pack-select");
    if (!sel) return;
    const cur = sel.value;
    sel.innerHTML =
      '<option value="">— select —</option>' +
      (names || [])
        .map(function (n) {
          return '<option value="' + esc(n) + '">' + esc(n) + "</option>";
        })
        .join("");
    if (cur && (names || []).indexOf(cur) >= 0) sel.value = cur;
  }

  function clonePreferences(prefs) {
    prefs = prefs || {};
    return {
      desirable: (prefs.desirable || []).slice(),
      neutral: (prefs.neutral || []).slice(),
      undesirable: (prefs.undesirable || []).slice(),
      reject: (prefs.reject || []).slice(),
    };
  }

  function applyScoringSnapshot(snap) {
    if (!snap) return;
    if (!state.settings) state.settings = {};
    state.settings.scoring = snap;

    const sc = state.scoring;
    sc.profileSynced = !!snap.profile_synced;
    sc.preferencesSynced = !!snap.preferences_synced;
    sc.referencesSynced = !!snap.references_synced;

    const prof = snap.profile || {};
    sc.profileReady = !!prof.ready;

    if (snap.profile_synced) {
      sc.preferencesUnlocked = true;
      sc.pendingFile = null;
      sc.pendingFileName = "";
      sc.dirtyProfile = false;
      sc.filename = prof.filename || "";
      sc.portfolio = prof.portfolio || "";
      sc.github = prof.github || "";
      sc.activitySphere = prof.activity_sphere || "";
      // Fresh prefs from profile analysis must show even if local dirty flag was set
      sc.dirtyPrefs = false;
      if (snap.preferences) sc.preferences = clonePreferences(snap.preferences);
    } else if (!sc.dirtyProfile) {
      sc.filename = prof.filename || "";
      sc.portfolio = prof.portfolio || "";
      sc.github = prof.github || "";
      sc.activitySphere = prof.activity_sphere || "";
    }

    if (!snap.profile_synced && (!prof.ready) && !sc.pendingFile) {
      sc.preferencesUnlocked = false;
    }

    if (!snap.profile_synced) {
      if (snap.preferences_synced) {
        sc.dirtyPrefs = false;
        sc.preferences = clonePreferences(snap.preferences);
      } else if (snap.preferences && !sc.dirtyPrefs) {
        sc.preferences = clonePreferences(snap.preferences);
      }
    }

    if (snap.references_synced) {
      sc.dirtyRefs = false;
      sc.refUrls = snap.references_urls || [];
    } else if (snap.references_urls && !sc.dirtyRefs) {
      sc.refUrls = snap.references_urls;
    }

    if (Array.isArray(snap.pack_names)) sc.packNames = snap.pack_names;

    const nameEl = document.getElementById("up-cv-name");
    if (nameEl) nameEl.textContent = sc.pendingFileName || sc.filename || "";

    const dzText = document.querySelector("#up-cv-dropzone .dropzone-text");
    if (dzText) {
      const shown = sc.pendingFileName || sc.filename || "";
      dzText.textContent = shown
        ? "CV: " + shown
        : "Drop CV here or browse — PDF / MD / TXT";
    }

    const port = document.getElementById("up-portfolio");
    const gh = document.getElementById("up-github");
    const sphEl = document.getElementById("up-sphere");
    if (port && !sc.dirtyProfile) port.value = sc.portfolio;
    if (gh && !sc.dirtyProfile) gh.value = sc.github;
    if (sphEl && !sc.dirtyProfile) sphEl.value = sc.activitySphere || "";

    const ccd = document.getElementById("opt-clear-check-days");
    if (ccd && snap.clear_check_days != null) ccd.value = String(snap.clear_check_days);

    PREF_BUCKETS.forEach(renderPrefTags);
    if (!sc.dirtyRefs) renderRefRows(sc.refUrls.length ? sc.refUrls : [""]);
    renderPackSelect(sc.packNames);
    updateScoringControls();
    updateScoringPanelVisuals();
  }

  function hydrateScoringFromSettings() {
    const s = state.settings || {};
    if (s.scoring) applyScoringSnapshot(s.scoring);
  }

  function renderLogBox() {
    const box = document.getElementById("log-box");
    if (box) box.textContent = (state.logs || []).slice(-80).join("\n");
  }

  function renderHotkeyBits() {
    const b1 = document.getElementById("hotkey-badge");
    const b2 = document.getElementById("hotkey-badge-2");
    const st = document.getElementById("hk-status");
    if (b1) b1.textContent = state.hotkey;
    if (b2) b2.textContent = state.hotkey;
    if (st) st.textContent = state.hkStatus || "";
  }

  function setPendingFile(file) {
    if (!file) return;
    state.scoring.pendingFile = file;
    state.scoring.pendingFileName = file.name || "";
    state.scoring.profileSynced = false;
    state.scoring.dirtyProfile = true;
    const nameEl = document.getElementById("up-cv-name");
    if (nameEl) nameEl.textContent = state.scoring.pendingFileName;
    const dzText = document.querySelector("#up-cv-dropzone .dropzone-text");
    if (dzText) dzText.textContent = "CV: " + state.scoring.pendingFileName;
    updateScoringControls();
    updateScoringPanelVisuals();
  }

  function baseOptPayload() {
    return {
      sound_enabled: document.getElementById("opt-sound").checked,
      dnd: document.getElementById("opt-dnd").checked,
      minimize_previous: document.getElementById("opt-min").checked,
      autostart_enabled: document.getElementById("opt-autostart").checked,
      scoring_mode: document.getElementById("opt-scoring").value,
    };
  }

  function handleScoringUploadEvent(data) {
    const panel = data.panel;
    const status = data.status;
    const elId = scoringStatusEl(panel);
    if (!elId) return;
    if (status === "loading") setUploadStatus(elId, "loading");
    else if (status === "ok") setUploadStatus(elId, "ok");
    else if (status === "error") {
      setUploadStatus(elId, "error");
      const el = document.getElementById(elId);
      if (el && data.error) el.title = String(data.error);
    } else setUploadStatus(elId, "");
  }

  function wireScoring() {
    PREF_BUCKETS.forEach(function (bucket) {
      const inp = document.getElementById("pref-input-" + bucket);
      if (!inp) return;
      inp.addEventListener("keydown", function (e) {
        if (e.key === "," || e.key === "Enter") {
          e.preventDefault();
          let val = inp.value;
          if (e.key === ",") val = val.replace(/,+$/, "");
          addPrefTag(bucket, val);
          inp.value = "";
        }
      });
    });

    const port = document.getElementById("up-portfolio");
    const gh = document.getElementById("up-github");
    const sph = document.getElementById("up-sphere");
    if (port) port.addEventListener("input", markProfileDirty);
    if (gh) gh.addEventListener("input", markProfileDirty);
    if (sph) sph.addEventListener("input", markProfileDirty);

    const dz = document.getElementById("up-cv-dropzone");
    const fileInput = document.getElementById("up-cv-file");
    const browseBtn = document.getElementById("btn-up-cv-browse");
    if (dz) {
      dz.addEventListener("dragover", function (e) {
        e.preventDefault();
        dz.classList.add("is-drag");
      });
      dz.addEventListener("dragleave", function () {
        dz.classList.remove("is-drag");
      });
      dz.addEventListener("drop", function (e) {
        e.preventDefault();
        dz.classList.remove("is-drag");
        const f = e.dataTransfer.files && e.dataTransfer.files[0];
        if (f) setPendingFile(f);
      });
    }
    if (browseBtn && fileInput) {
      browseBtn.addEventListener("click", function (e) {
        e.preventDefault();
        e.stopPropagation();
        fileInput.click();
      });
      fileInput.addEventListener("change", function () {
        const f = fileInput.files && fileInput.files[0];
        if (f) setPendingFile(f);
        fileInput.value = "";
      });
    }

    const btnClearCv = document.getElementById("up-cv-clear");
    if (btnClearCv) btnClearCv.onclick = function () {
      send("clearProfile");
    };

    const btnProf = document.getElementById("btn-up-profile");
    if (btnProf) {
      btnProf.onclick = function () {
        setUploadStatus("up-profile-status", "loading");
        const portfolio = document.getElementById("up-portfolio").value.trim();
        const github = document.getElementById("up-github").value.trim();
        const sphereEl = document.getElementById("up-sphere");
        const activitySphere = sphereEl ? sphereEl.value.trim() : "";
        const pf = state.scoring.pendingFile;
        if (pf) {
          readFileAsDataURL(pf)
            .then(function (dataUrl) {
              send("uploadProfile", {
                resume_b64: String(dataUrl).replace(/^data:[^;]+;base64,/, ""),
                resume_filename: pf.name || state.scoring.pendingFileName || "resume.pdf",
                portfolio_url: portfolio,
                github_url: github,
                activity_sphere: activitySphere,
              });
            })
            .catch(function () {
              setUploadStatus("up-profile-status", "");
            });
        } else {
          send("uploadProfile", {
            resume_b64: "",
            resume_filename: "",
            portfolio_url: portfolio,
            github_url: github,
            activity_sphere: activitySphere,
          });
        }
      };
    }

    const btnPref = document.getElementById("btn-up-preferences");
    if (btnPref) {
      btnPref.onclick = function () {
        setUploadStatus("up-pref-status", "loading");
        send("uploadPreferences", { preferences: collectPreferencesFromDOM() });
      };
    }

    const btnRef = document.getElementById("btn-up-references");
    if (btnRef) {
      btnRef.onclick = function () {
        setUploadStatus("up-ref-status", "loading");
        send("uploadReferences", { urls: collectRefUrls() });
      };
    }

    const btnRefAdd = document.getElementById("btn-ref-add");
    if (btnRefAdd) {
      btnRefAdd.onclick = function () {
        const list = document.getElementById("ref-list");
        if (!list) return;
        const row = document.createElement("div");
        row.className = "ref-row";
        row.innerHTML =
          '<input class="input" type="url" placeholder="https://…" />' +
          '<button class="x-row" type="button" aria-label="Remove reference">×</button>';
        list.appendChild(row);
        wireRefRows();
        row.querySelector("input").focus();
      };
    }

    const btnPackSave = document.getElementById("btn-pack-save");
    if (btnPackSave) {
      btnPackSave.onclick = function () {
        const name = document.getElementById("pack-name").value.trim();
        if (name) send("savePack", { name: name });
      };
    }
    const btnPackLoad = document.getElementById("btn-pack-load");
    if (btnPackLoad) {
      btnPackLoad.onclick = function () {
        const name = document.getElementById("pack-select").value;
        if (name) send("loadPack", { name: name });
      };
    }
    const btnPackImport = document.getElementById("btn-pack-import");
    if (btnPackImport) {
      btnPackImport.onclick = function () {
        let inp = document.getElementById("pack-import-file");
        if (!inp) {
          inp = document.createElement("input");
          inp.type = "file";
          inp.accept = ".json";
          inp.id = "pack-import-file";
          inp.style.display = "none";
          document.body.appendChild(inp);
          inp.addEventListener("change", function () {
            const f = inp.files && inp.files[0];
            if (!f) return;
            readFileAsDataURL(f)
              .then(function (dataUrl) {
                send("importPack", {
                  filename: f.name || "pack.json",
                  pack_b64: String(dataUrl).replace(/^data:[^;]+;base64,/, ""),
                });
              })
              .finally(function () {
                inp.value = "";
              });
          });
        }
        inp.click();
      };
    }

    const btnPackDownload = document.getElementById("btn-pack-download");
    if (btnPackDownload) {
      btnPackDownload.onclick = function () {
        const sel = document.getElementById("pack-select");
        const named = (sel && sel.value) || "";
        const typed = (document.getElementById("pack-name") || {}).value || "";
        send("downloadPack", { name: named || String(typed).trim() || "" });
      };
    }

    const ccd = document.getElementById("opt-clear-check-days");
    if (ccd) {
      ccd.addEventListener("change", function () {
        clearTimeout(clearCheckDaysTimer);
        clearCheckDaysTimer = setTimeout(function () {
          const days = parseInt(ccd.value, 10);
          send("setOpt", Object.assign({}, baseOptPayload(), { clear_check_days: days > 0 ? days : 7 }));
        }, 400);
      });
    }

    renderRefRows([""]);
    updateScoringControls();
    updateScoringPanelVisuals();
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
    if (kind === "visited") return "pill-seen";
    return "pill-new";
  }

  function statusClass(kind) {
    if (kind === "pointer") return "is-pointer";
    if (kind === "invite") return "is-invite";
    if (kind === "apply") return "is-apply";
    if (kind === "visited") return "is-visited";
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
          '<span class="vac-letter' +
          (it.letterStatus === "writing" ? " is-busy" : "") +
          (it.letterStatus === "fail" ? " is-fail" : "") +
          (it.letterStatus === "ok" || it.letterStatus === "cursor" ? " is-ok" : "") +
          '">' +
          esc(it.letter || "") +
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
      const lst0 = document.getElementById("d-letter-status");
      if (lst0) {
        lst0.textContent = "—";
        lst0.className = "letter-status";
      }
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
    const lst = document.getElementById("d-letter-status");
    if (lst) {
      const st = d.letterStatus || "";
      const labels = {
        writing: "Writing…",
        queued: "Queued",
        pending: "Pending",
        ok: "Ready",
        cursor: "Ready",
        local: "Local",
        fail: "Failed",
      };
      lst.textContent = labels[st] || (d.letter ? "Ready" : "—");
      lst.className =
        "letter-status" +
        (st === "writing" ? " is-busy" : "") +
        (st === "fail" ? " is-fail" : "") +
        (st === "ok" || st === "cursor" ? " is-ok" : "");
    }
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
    const optSound = document.getElementById("opt-sound");
    const optDnd = document.getElementById("opt-dnd");
    const optMin = document.getElementById("opt-min");
    const optAuto = document.getElementById("opt-autostart");
    if (optSound) optSound.checked = !!s.sound_enabled;
    if (optDnd) optDnd.checked = !!s.dnd;
    if (optMin) optMin.checked = !!s.minimize_previous;
    if (optAuto) optAuto.checked = !!s.autostart_enabled;
    const scoring = document.getElementById("opt-scoring");
    if (scoring) {
      const m = s.scoring_mode || "hybrid";
      scoring.value = m === "rules" || m === "cursor" ? m : "hybrid";
    }
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
    const ccd = document.getElementById("opt-clear-check-days");
    if (ccd && s.clear_check_days != null) ccd.value = String(s.clear_check_days);
    renderHotkeyBits();
    renderLogBox();
    // Do NOT re-hydrate scoring here — log/hotkey updates must not wipe a fresh scoring snapshot.
  }

  function renderBusy() {
    document.getElementById("btn-search").disabled = !!state.busy.search;
    const cc = document.getElementById("btn-clear-check");
    if (cc) cc.disabled = !!state.busy.search;
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
        if (data.items) state.items = data.items;
        if (data.counts) state.counts = data.counts;
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
        if (data.scoring) applyScoringSnapshot(data.scoring);
      } else if (event === "scoring") {
        if (data.uploadStatus) {
          const us = data.uploadStatus;
          const elId = scoringStatusEl(us.panel);
          if (elId) setUploadStatus(elId, us.mode || "");
        }
        applyScoringSnapshot(data);
      } else if (event === "scoringUpload") {
        handleScoringUploadEvent(data);
      } else if (event === "log") {
        if (data.line) state.logs.push(data.line);
        if (data.lines) state.logs = data.lines;
        renderLogBox();
      } else if (event === "hotkey") {
        if (data.label) state.hotkey = data.label;
        if (data.status != null) state.hkStatus = data.status;
        renderHotkeyBits();
      } else if (event === "busy") {
        state.busy = Object.assign({}, state.busy, data);
        renderBusy();
      } else if (event === "activity") {
        const bar = document.getElementById("activity-bar");
        const txt = document.getElementById("activity-text");
        if (!bar || !txt) return;
        if (data.busy) {
          bar.hidden = false;
          bar.classList.add("is-busy");
          txt.textContent = data.line || "Working…";
        } else {
          bar.classList.remove("is-busy");
          if (data.line) {
            bar.hidden = false;
            txt.textContent = data.line;
          } else {
            bar.hidden = true;
            txt.textContent = "—";
          }
        }
      } else if (event === "page") {
        showPage(data.name || "queue");
      }
    },
  };

  function wire() {
    document.getElementById("btn-search").onclick = () => send("search");
    const btnClear = document.getElementById("btn-clear-check");
    if (btnClear) btnClear.onclick = () => send("clearCheck");
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
    wireScoring();
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
