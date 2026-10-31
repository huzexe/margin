// Unlock page: shown on other devices (phone, tablet) until the PIN is entered.

const form = document.getElementById('unlock-form');
const error = document.getElementById('unlock-error');
const submit = document.getElementById('unlock-submit');

// Only go back to a page on this site
function nextPage() {
  // Let the browser resolve it, so tricks like "/\other-site.com" (read as //other-site.com) are caught
  try {
    const next = new URL(new URLSearchParams(location.search).get('next') || '/', location.origin);
    if (next.origin === location.origin) return next.pathname + next.search + next.hash;
  } catch { /* not a valid address */ }
  return '/';
}

form.addEventListener('submit', async e => {
  e.preventDefault();
  error.hidden = true;
  submit.disabled = true;
  try {
    const res = await fetch('/api/unlock', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin: document.getElementById('pin').value }),
    });
    if (res.ok) {
      location.replace(nextPage());
      return;
    }
    const data = await res.json().catch(() => null);
    error.textContent = data?.detail || "Couldn't unlock. Try again.";
  } catch {
    error.textContent = "Can't reach Margin. Check that the computer running it is on and on the same Wi-Fi.";
  }
  error.hidden = false;
  submit.disabled = false;
  document.getElementById('pin').select();
});
