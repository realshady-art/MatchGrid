(function () {
  function readJsonScript(id) {
    const el = document.getElementById(id);
    if (!el || !el.textContent.trim()) return null;
    try {
      return JSON.parse(el.textContent);
    } catch {
      return null;
    }
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function escapeAttr(s) {
    return escapeHtml(s).replace(/'/g, "&#39;");
  }

  const pitch = document.querySelector("[data-pitch]");
  const tokensLayer = document.querySelector("[data-tokens-layer]");
  const poolList = document.querySelector("[data-pool-list]");
  const searchInput = document.querySelector("[data-pool-search]");
  const leagueSelect = document.querySelector("[data-pool-league]");
  const clubSelect = document.querySelector("[data-pool-club]");
  const posGroupSelect = document.querySelector("[data-pool-pos-group]");
  const strengthMeta = document.querySelector("[data-strength-meta]");
  const CLUBS_BY_LEAGUE = readJsonScript("board-clubs-by-league") || {};
  const ALL_CLUBS = readJsonScript("board-all-clubs");
  const allClubsList = Array.isArray(ALL_CLUBS) ? ALL_CLUBS : [];
  let activeSide = "home";

  const state = { home: [], away: [] };

  let dragToken = null;

  function setActiveSide(side) {
    activeSide = side === "away" ? "away" : "home";
    document.querySelectorAll("[data-side-pick]").forEach((btn) => {
      btn.classList.toggle("is-active", btn.getAttribute("data-side-pick") === activeSide);
    });
  }

  document.querySelectorAll("[data-side-pick]").forEach((btn) => {
    btn.addEventListener("click", () => setActiveSide(btn.getAttribute("data-side-pick")));
  });

  document.querySelector("[data-clear-home]")?.addEventListener("click", () => {
    state.home = [];
    renderTokens();
    schedulePredict();
  });
  document.querySelector("[data-clear-away]")?.addEventListener("click", () => {
    state.away = [];
    renderTokens();
    schedulePredict();
  });

  function faceUrl(playerId) {
    return `/api/board/player-photo/${encodeURIComponent(playerId)}`;
  }

  function letterAvatarDataUrl(name) {
    const letter = (name || "?").trim().charAt(0).toUpperCase() || "?";
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128"><rect fill="#121820" width="128" height="128"/><text x="64" y="82" text-anchor="middle" fill="#2ee6d6" font-size="58" font-family="system-ui,Segoe UI,sans-serif" font-weight="700">${letter}</text></svg>`;
    return `data:image/svg+xml,${encodeURIComponent(svg)}`;
  }

  function bindFaceImg(img, playerId, name) {
    const primary = faceUrl(playerId);
    const remoteFallback = `https://ui-avatars.com/api/?background=121820&color=2ee6d6&size=256&bold=true&name=${encodeURIComponent(name || "?")}`;
    img.loading = "lazy";
    img.decoding = "async";
    img.alt = name || "";
    img.src = primary;
    img.addEventListener("error", () => {
      const step = img.dataset.faceStep || "0";
      if (step === "0") {
        img.dataset.faceStep = "1";
        img.src = remoteFallback;
      } else if (step === "1") {
        img.dataset.faceStep = "2";
        img.src = letterAvatarDataUrl(name);
      }
    });
  }

  let poolItems = [];
  let fetchTimer;

  function rebuildClubSelect() {
    if (!clubSelect) return;
    const prev = clubSelect.value;
    const lg = leagueSelect?.value || "";
    const list =
      lg && Array.isArray(CLUBS_BY_LEAGUE[lg]) && CLUBS_BY_LEAGUE[lg].length
        ? CLUBS_BY_LEAGUE[lg]
        : allClubsList;
    clubSelect.innerHTML =
      '<option value="">全部俱乐部</option>' +
      list
        .map(
          (c) =>
            `<option value="${escapeAttr(c)}" title="${escapeAttr(c)}">${escapeHtml(c)}</option>`
        )
        .join("");
    if (prev && list.includes(prev)) clubSelect.value = prev;
  }

  function formatClubLine(club) {
    return String(club || "")
      .trim()
      .replace(/\s*,\s*/g, " · ")
      .replace(/\s*\/\s*/g, " · ") || "—";
  }

  async function loadPool() {
    const q = searchInput?.value?.trim() || "";
    const league = leagueSelect?.value || "";
    const club = clubSelect?.value || "";
    const posGroup = posGroupSelect?.value || "";
    const params = new URLSearchParams({ limit: "200" });
    if (q) params.set("q", q);
    if (league) params.set("league", league);
    if (club) params.set("club", club);
    if (posGroup) params.set("pos_group", posGroup);
    const res = await fetch(`/api/board/players?${params}`);
    if (!res.ok) return;
    const data = await res.json();
    poolItems = data.items || [];
    renderPool();
  }

  function renderPool() {
    if (!poolList) return;
    poolList.innerHTML = poolItems
      .map((p) => {
        const pid = escapeAttr(p.id);
        return `
      <div class="pool-row" draggable="true" data-player-id="${pid}">
        <div class="pool-row__face-wrap">
          <img class="pool-row__face" width="48" height="48" data-player-id="${pid}" alt="" />
        </div>
        <div class="pool-row__body">
          <div class="pool-row__name">${escapeHtml(p.name)}</div>
          <div class="pool-row__meta">${escapeHtml(formatClubLine(p.club))} · ${escapeHtml(p.league)} · ${escapeHtml(p.position)}</div>
        </div>
        <div class="pool-row__rating">${Number(p.rating).toFixed(0)}</div>
      </div>`;
      })
      .join("");

    poolList.querySelectorAll(".pool-row__face").forEach((img) => {
      const id = img.getAttribute("data-player-id");
      const player = poolItems.find((x) => x.id === id);
      if (player) bindFaceImg(img, player.id, player.name);
    });

    poolList.querySelectorAll(".pool-row").forEach((row) => {
      row.addEventListener("dragstart", (ev) => {
        const id = row.getAttribute("data-player-id");
        const player = poolItems.find((x) => x.id === id);
        if (!player) return;
        ev.dataTransfer.setData("application/x-match-board", JSON.stringify({ kind: "pool", player, side: activeSide }));
        ev.dataTransfer.effectAllowed = "copy";
      });
    });
  }

  function normCoord(clientX, clientY) {
    const r = pitch.getBoundingClientRect();
    const x = (clientX - r.left) / r.width;
    const y = (clientY - r.top) / r.height;
    return { x: clamp(x), y: clamp(y) };
  }

  function clamp(t) {
    return Math.max(0, Math.min(1, t));
  }

  function uid() {
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  }

  pitch?.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    ev.dataTransfer.dropEffect = ev.dataTransfer.effectAllowed === "move" ? "move" : "copy";
  });

  pitch?.addEventListener("drop", (ev) => {
    ev.preventDefault();
    const raw = ev.dataTransfer.getData("application/x-match-board");
    if (!raw) return;
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch {
      return;
    }
    const { x, y } = normCoord(ev.clientX, ev.clientY);
    if (payload.kind === "pool") {
      const side = payload.side === "away" ? "away" : "home";
      state[side].push({
        instanceId: uid(),
        player: payload.player,
        x,
        y,
      });
    } else if (payload.kind === "token") {
      const side = payload.side === "away" ? "away" : "home";
      const list = state[side];
      const token = list.find((t) => t.instanceId === payload.instanceId);
      if (token) {
        token.x = x;
        token.y = y;
      }
    }
    renderTokens();
    schedulePredict();
  });

  function onDocumentPointerMove(ev) {
    if (!dragToken || ev.pointerId !== dragToken.pointerId) return;
    const rect = pitch.getBoundingClientRect();
    const dx = (ev.clientX - dragToken.startCX) / rect.width;
    const dy = (ev.clientY - dragToken.startCY) / rect.height;
    let x = clamp(dragToken.origX + dx);
    let y = clamp(dragToken.origY + dy);
    const list = state[dragToken.side];
    const tok = list.find((t) => t.instanceId === dragToken.instanceId);
    if (tok) {
      tok.x = x;
      tok.y = y;
    }
    dragToken.el.style.left = `${x * 100}%`;
    dragToken.el.style.top = `${y * 100}%`;
  }

  function onDocumentPointerUp(ev) {
    if (!dragToken || ev.pointerId !== dragToken.pointerId) return;
    document.removeEventListener("pointermove", onDocumentPointerMove);
    document.removeEventListener("pointerup", onDocumentPointerUp);
    document.removeEventListener("pointercancel", onDocumentPointerUp);

    const rect = pitch.getBoundingClientRect();
    const cx = ev.clientX;
    const cy = ev.clientY;
    const outside = cx < rect.left - 12 || cx > rect.right + 12 || cy < rect.top - 12 || cy > rect.bottom + 12;
    if (outside) {
      state[dragToken.side] = state[dragToken.side].filter((t) => t.instanceId !== dragToken.instanceId);
      renderTokens();
    }
    dragToken = null;
    schedulePredict();
  }

  function attachTokenPointerHandlers(el, side, t) {
    el.addEventListener("pointerdown", (ev) => {
      if (ev.button !== 0) return;
      ev.preventDefault();
      dragToken = {
        el,
        side,
        instanceId: t.instanceId,
        pointerId: ev.pointerId,
        startCX: ev.clientX,
        startCY: ev.clientY,
        origX: t.x,
        origY: t.y,
      };
      document.addEventListener("pointermove", onDocumentPointerMove);
      document.addEventListener("pointerup", onDocumentPointerUp);
      document.addEventListener("pointercancel", onDocumentPointerUp);
    });

    el.addEventListener("dblclick", (ev) => {
      ev.preventDefault();
      state[side] = state[side].filter((x) => x.instanceId !== t.instanceId);
      renderTokens();
      schedulePredict();
    });
  }

  function renderTokens() {
    if (!tokensLayer) return;
    tokensLayer.innerHTML = "";
    const frag = document.createDocumentFragment();

    function addTokens(side) {
      for (const t of state[side]) {
        const el = document.createElement("div");
        el.className = `pitch-token pitch-token--${side}`;
        el.style.left = `${t.x * 100}%`;
        el.style.top = `${t.y * 100}%`;
        el.innerHTML = `
          <div class="pitch-token__inner">
            <img class="pitch-token__face" width="56" height="56" alt="${escapeAttr(t.player.name)}" />
            <div class="pitch-token__text">
              <span class="pitch-token__name">${escapeHtml(t.player.name)}</span>
              <span class="pitch-token__rating">${Number(t.player.rating).toFixed(0)}</span>
            </div>
          </div>`;
        const img = el.querySelector(".pitch-token__face");
        bindFaceImg(img, t.player.id, t.player.name);
        attachTokenPointerHandlers(el, side, t);
        frag.appendChild(el);
      }
    }

    addTokens("home");
    addTokens("away");
    tokensLayer.appendChild(frag);
  }

  let predictTimer;
  function schedulePredict() {
    window.clearTimeout(predictTimer);
    predictTimer = window.setTimeout(runPredict, 380);
  }

  async function runPredict() {
    const body = {
      home: state.home.map((t) => ({ player_id: t.player.id, x: t.x, y: t.y })),
      away: state.away.map((t) => ({ player_id: t.player.id, x: t.x, y: t.y })),
    };
    try {
      const res = await fetch("/api/board/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) return;
      const data = await res.json();
      updateHud(data);
    } catch {
      /* offline */
    }
  }

  function updateHud(data) {
    const probs = data.probabilities || {};
    const h = (100 * (probs.H || 0)).toFixed(1);
    const d = (100 * (probs.D || 0)).toFixed(1);
    const a = (100 * (probs.A || 0)).toFixed(1);
    document.querySelector('[data-pct="H"]').textContent = `${h}%`;
    document.querySelector('[data-pct="D"]').textContent = `${d}%`;
    document.querySelector('[data-pct="A"]').textContent = `${a}%`;
    document.querySelector('.predict-bar[data-outcome="H"] .predict-bar__fill').style.width = `${h}%`;
    document.querySelector('.predict-bar[data-outcome="D"] .predict-bar__fill').style.width = `${d}%`;
    document.querySelector('.predict-bar[data-outcome="A"] .predict-bar__fill').style.width = `${a}%`;
    const ts = data.team_strength || {};
    if (strengthMeta) {
      strengthMeta.textContent = `Strength · Home ${ts.home ?? "—"} · Away ${ts.away ?? "—"} · Call ${data.prediction ?? "—"}`;
    }
  }

  searchInput?.addEventListener("input", () => {
    window.clearTimeout(fetchTimer);
    fetchTimer = window.setTimeout(loadPool, 220);
  });
  leagueSelect?.addEventListener("change", () => {
    rebuildClubSelect();
    loadPool();
  });
  clubSelect?.addEventListener("change", loadPool);
  posGroupSelect?.addEventListener("change", loadPool);

  rebuildClubSelect();
  loadPool();
  runPredict();
})();
