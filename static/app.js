function startClock() {
  const clock = document.querySelector("[data-live-clock]");
  if (!clock) return;

  const render = () => {
    clock.textContent = new Date().toLocaleString();
  };

  render();
  window.setInterval(render, 1000);
}

async function refreshTimeline() {
  const timeline = document.querySelector("[data-timeline]");
  if (!timeline) return;

  try {
    const response = await fetch("/api/timeline");
    if (!response.ok) return;
    const payload = await response.json();
    if (!payload.items?.length) return;

    timeline.innerHTML = payload.items
      .map(
        (item) => `
          <a class="timeline-item" href="/predictions/${item.id}">
            <div class="timeline-marker"></div>
            <div class="timeline-content">
              <div class="timeline-title">${item.home_team} vs ${item.away_team}</div>
              <div class="timeline-subtitle">Prediction: ${item.prediction}</div>
              <div class="timeline-meta">${item.created_at}</div>
            </div>
          </a>
        `
      )
      .join("");
  } catch (_) {
    // Ignore transient refresh failures and keep the current timeline view.
  }
}

startClock();
refreshTimeline();
window.setInterval(refreshTimeline, 15000);
