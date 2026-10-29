// Settings page: default options, appearance, backup and restore.

import { api } from './api.js';
import { debounce, el, errorNotice, setupThemeToggle, toast } from './ui.js';

const $ = id => document.getElementById(id);
const OPTION_KEYS = ['simplify', 'diagrams', 'flashcards', 'applications'];

/* ---------- Default options ---------- */

function pressed(groupId, value) {
  for (const b of $(groupId).querySelectorAll('button')) b.setAttribute('aria-pressed', String(b.dataset.value === value));
}

function currentDefaults() {
  const options = Object.fromEntries(OPTION_KEYS.map(k => [k, $(`def-${k}`).checked]));
  options.detail = $('def-detail').querySelector('[aria-pressed="true"]').dataset.value;
  return options;
}

const saveDefaults = debounce(async () => {
  $('defaults-status').textContent = 'Saving…';
  try {
    await api('/api/settings', { method: 'PUT', body: { default_options: currentDefaults() } });
    $('defaults-status').textContent = 'Saved';
  } catch (err) {
    $('defaults-status').textContent = '';
    toast(err.message, { error: true });
  }
}, 300);

async function loadDefaults() {
  const { default_options: o } = await api('/api/settings');
  for (const k of OPTION_KEYS) $(`def-${k}`).checked = Boolean(o[k]);
  pressed('def-detail', o.detail);
}

for (const k of OPTION_KEYS) $(`def-${k}`).addEventListener('change', saveDefaults);
$('def-detail').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (b) { pressed('def-detail', b.dataset.value); saveDefaults(); }
});

/* ---------- Appearance ---------- */

function themeChoice() {
  try { return localStorage.getItem('margin-theme') || 'system'; } catch { return 'system'; }
}

function setupTheme() {
  const root = document.documentElement;
  const toggle = $('theme-toggle');
  setupThemeToggle(toggle);
  pressed('theme-choice', themeChoice());
  toggle.addEventListener('click', () => pressed('theme-choice', themeChoice()));
  $('theme-choice').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    const value = b.dataset.value;
    try {
      if (value === 'system') localStorage.removeItem('margin-theme');
      else localStorage.setItem('margin-theme', value);
    } catch { /* not saved; still applies to this page */ }
    if (value === 'system') delete root.dataset.theme;
    else root.dataset.theme = value;
    pressed('theme-choice', value);
    toggle.dispatchEvent(new Event('margin:repaint'));
  });
}

/* ---------- Backup ---------- */

async function backupSummary() {
  const [notes, subjects] = await Promise.all([api('/api/notes'), api('/api/subjects')]);
  const n = notes.length, s = subjects.length;
  $('backup-summary').textContent = `${n} ${n === 1 ? 'note' : 'notes'}, ${s} ${s === 1 ? 'subject' : 'subjects'}`;
}

/* ---------- Restore ---------- */

let backupText = null;

function restorePanel(...children) {
  $('restore-panel').replaceChildren(...children);
}

$('restore-file').addEventListener('change', async () => {
  const file = $('restore-file').files[0];
  $('restore-file').value = ''; // allow choosing the same file again
  if (!file) return;
  $('restore-file-name').textContent = file.name;
  let data;
  try {
    backupText = await file.text();
    data = JSON.parse(backupText);
    if (data?.app !== 'margin' || !Array.isArray(data.notes)) throw new Error();
  } catch {
    backupText = null;
    restorePanel(errorNotice("This isn't a Margin backup", 'Choose a file made with Download backup (it ends in .json).'));
    return;
  }

  const when = data.exported_at ? new Date(data.exported_at).toLocaleString() : 'an unknown date';
  const n = data.notes.length, s = (data.subjects || []).length;
  restorePanel(el('div', { class: 'confirm-panel restore-choice' },
    el('p', {}, `Backup from ${when}: ${n} ${n === 1 ? 'note' : 'notes'}, ${s} ${s === 1 ? 'subject' : 'subjects'}.`),
    el('div', { class: 'restore-options' },
      el('div', {},
        el('button', { class: 'btn btn-primary btn-sm', type: 'button', onclick: () => restore('merge') }, 'Add to my library'),
        el('p', { class: 'field-hint' }, 'Keeps your current notes and adds the ones from the backup. Restoring the same backup twice creates copies.')),
      el('div', {},
        el('button', { class: 'btn btn-danger btn-sm', type: 'button', onclick: confirmReplace }, 'Replace everything'),
        el('p', { class: 'field-hint' }, 'Deletes all current notes and subjects, then loads the backup.')),
    ),
    el('button', { class: 'link-button', type: 'button', onclick: () => { restorePanel(); $('restore-file-name').textContent = ''; } }, 'Cancel'),
  ));
});

function confirmReplace() {
  restorePanel(el('div', { class: 'confirm-inline', role: 'alertdialog' },
    el('p', {}, "Delete all current notes and subjects and replace them with the backup? This can't be undone. Download a backup of your current library first if you might need it."),
    el('div', { class: 'confirm-actions' },
      el('button', { class: 'btn btn-danger btn-sm', type: 'button', onclick: () => restore('replace') }, 'Delete and replace'),
      el('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => $('restore-file').dispatchEvent(new Event('change')) }, 'Back'),
    ),
  ));
}

async function restore(mode) {
  if (!backupText) return;
  restorePanel(el('p', { class: 'status-line' }, 'Restoring…'));
  let res;
  try {
    res = await fetch(`/api/restore?mode=${mode}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: backupText,
    });
  } catch {
    restorePanel(errorNotice("Couldn't restore", "Can't reach Margin. Check that the app is still running in the terminal."));
    return;
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    restorePanel(errorNotice("Couldn't restore", data?.detail || `Something went wrong (error ${res.status}).`));
    return;
  }
  backupText = null;
  $('restore-file-name').textContent = '';
  const added = `${data.notes} ${data.notes === 1 ? 'note' : 'notes'}`;
  restorePanel(el('p', { class: 'restore-done' }, mode === 'replace'
    ? `Done. Your library now contains the ${added} from the backup. `
    : `Done. Added ${added}. `, el('a', { href: '/' }, 'Go to library')));
  backupSummary().catch(() => {});
  loadDefaults().catch(() => {});
}

/* ---------- Phone access ---------- */

async function phonePanel() {
  const panel = $('phone-panel');
  let s;
  try { s = await api('/api/phone'); } catch { panel.replaceChildren(); return; }

  if (!s.enabled) {
    panel.replaceChildren(
      el('p', {}, 'Off. Margin only opens on this computer.'),
      el('p', { class: 'field-hint' }, 'To use it on your phone or tablet at home (same Wi-Fi), see “Phone access” in the README. In short: add MARGIN_PHONE_ACCESS=on and a MARGIN_PIN to the .env file, restart Margin, and allow the port in the firewall.'),
    );
    return;
  }
  const children = [
    el('p', {}, 'On. On your phone or tablet (same Wi-Fi), open:'),
    s.url ? el('p', { class: 'phone-url' }, s.url) : el('p', { class: 'field-error' }, "This computer doesn't seem to be on a network right now."),
    el('p', { class: 'field-hint' }, 'Each device asks for the PIN once and then stays unlocked for 30 days. The connection is not encrypted, so only use this on your own home network, never on public Wi-Fi.'),
  ];
  if (s.this_computer) {
    const button = el('button', { class: 'btn btn-sm', type: 'button', onclick: async () => {
      button.disabled = true;
      try {
        await api('/api/phone/sign-out-all', { method: 'POST' });
        toast('All phones and tablets are signed out. They need the PIN again.');
      } catch (err) { toast(err.message, { error: true }); }
      button.disabled = false;
    } }, 'Sign out all phones');
    children.push(el('div', { class: 'settings-row' }, button));
  }
  panel.replaceChildren(...children);
}

/* ---------- Start ---------- */

phonePanel();

setupTheme();
loadDefaults().catch(err => toast(err.message, { error: true }));
backupSummary().catch(() => {});
$('backup-download').addEventListener('click', () => toast('Downloading backup to your Downloads folder…'));
