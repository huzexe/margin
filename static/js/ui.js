// Shared UI helpers: icons, dates, element builder, theme toggle, toasts.

// "Still here" signal: lets Margin stop by itself after its last window is closed
// (only when it was started by the app launcher). Hidden tabs may send it less often; that's fine.
function heartbeat() {
  fetch('/api/heartbeat', { method: 'POST', keepalive: true }).catch(() => {});
}
heartbeat();
setInterval(heartbeat, 30_000);
document.addEventListener('visibilitychange', () => { if (!document.hidden) heartbeat(); });

const ICONS = {
  plus: '<path d="M12 5v14M5 12h14"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  pencil: '<path d="M4 20h4L19 9l-4-4L4 16v4z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  moon: '<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  back: '<path d="M15 6l-6 6 6 6"/>',
  alert: '<circle cx="12" cy="12" r="9"/><path d="M12 8v5M12 16.5v.01"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 4v5h-5"/>',
};

export function icon(name) {
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name]}</svg>`;
}

// Build an element: el('a', { class: 'x', href: '/' }, 'text', otherNode)
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === false || value == null) continue;
    if (key === 'html') node.innerHTML = value; // only used with trusted markup such as icon()
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

export function formatDate(iso) {
  const date = new Date(iso);
  const today = new Date();
  const startOf = d => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((startOf(today) - startOf(date)) / 86_400_000);
  if (days === 0) return date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  if (days === 1) return 'Yesterday';
  const opts = { month: 'short', day: 'numeric' };
  if (date.getFullYear() !== today.getFullYear()) opts.year = 'numeric';
  return date.toLocaleDateString(undefined, opts);
}

export function debounce(fn, ms) {
  let timer;
  const wrapped = (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

// Theme toggle button in the top bar
export function setupThemeToggle(button) {
  const root = document.documentElement;
  const isDark = () => root.dataset.theme
    ? root.dataset.theme === 'dark'
    : matchMedia('(prefers-color-scheme: dark)').matches;
  const paint = () => {
    button.innerHTML = icon(isDark() ? 'sun' : 'moon');
    button.setAttribute('aria-label', isDark() ? 'Switch to light mode' : 'Switch to dark mode');
    button.title = button.getAttribute('aria-label');
  };
  button.addEventListener('click', () => {
    root.dataset.theme = isDark() ? 'light' : 'dark';
    try { localStorage.setItem('margin-theme', root.dataset.theme); } catch { /* not saved */ }
    paint();
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', paint);
  button.addEventListener('margin:repaint', paint); // theme changed elsewhere (Settings page)
  paint();
}

// Error box with an optional "Try again" button
export function errorNotice(title, message, onRetry) {
  const box = el('div', { class: 'notice notice-error', role: 'alert', html: icon('alert') });
  box.append(
    el('div', { class: 'notice-body' }, el('div', { class: 'notice-title' }, title), el('div', {}, message)),
    onRetry && el('button', { class: 'btn btn-sm', type: 'button', onclick: onRetry }, 'Try again'),
  );
  return box;
}

// Short message at the bottom of the screen (errors and confirmations).
// action: { label, onClick } adds a button, e.g. Undo; the message then stays longer.
export function toast(message, { error = false, action = null, duration } = {}) {
  let region = document.getElementById('toasts');
  if (!region) {
    region = el('div', { id: 'toasts', class: 'toasts', role: 'status', 'aria-live': 'polite' });
    document.body.append(region);
  }
  const item = el('div', { class: 'toast' + (error ? ' toast-error' : '') }, el('span', {}, message));
  const close = () => item.remove();
  if (action) {
    item.append(el('button', {
      class: 'toast-action', type: 'button',
      onclick: () => { close(); action.onClick(); },
    }, action.label));
  }
  region.append(item);
  setTimeout(close, duration ?? (action ? 15000 : error ? 6000 : 3000));
  return close;
}
