(function () {
  const clock = document.querySelector("[data-live-clock]");
  if (!clock) return;
  const tick = () => {
    clock.textContent = new Date().toLocaleString();
  };
  tick();
  window.setInterval(tick, 1000);
})();
