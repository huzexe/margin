// Loaded in <head> before the page draws, so a saved dark theme never flashes light.
(function () {
  try {
    var saved = localStorage.getItem('margin-theme');
    if (saved === 'light' || saved === 'dark') document.documentElement.dataset.theme = saved;
  } catch (e) { /* storage blocked: follow the system setting */ }
})();
