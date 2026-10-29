// Export page: choose PDF settings, see the real PDF as a preview, download it.

import { api } from './api.js';
import { debounce, el, errorNotice, setupThemeToggle } from './ui.js';

const $ = id => document.getElementById(id);
const noteId = Number(location.pathname.match(/^\/notes\/(\d+)\/export$/)?.[1]);
let pdfUrl = null;   // blob: URL of the current preview
let fileName = 'note.pdf';
let requestId = 0;

function segmented(id) {
  const group = $(id);
  group.addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    for (const x of group.querySelectorAll('button')) x.setAttribute('aria-pressed', String(x === b));
    refresh();
  });
  return () => group.querySelector('[aria-pressed="true"]').dataset.value;
}
const size = segmented('set-size');
const margins = segmented('set-margins');

function settings() {
  return new URLSearchParams({
    toc: $('set-toc').checked ? 1 : 0,
    flashcards: $('set-flashcards').checked ? 1 : 0,
    rough: $('set-rough').checked ? 1 : 0,
    size: size(),
    margins: margins(),
  });
}

function setBusy(busy) {
  $('preview-progress').hidden = !busy;
  $('download').disabled = busy || !pdfUrl;
  if (busy) {
    $('preview-status').hidden = false;
    $('preview-status').textContent = 'Preparing preview…';
  }
}

async function makePdf() {
  const id = ++requestId;
  setBusy(true);
  $('export-info').textContent = '';
  let res;
  try {
    res = await fetch(`/api/notes/${noteId}/pdf?${settings()}`);
  } catch {
    if (id === requestId) showError("Can't reach Margin. Check that the app is still running in the terminal.");
    return;
  }
  if (id !== requestId) return; // settings changed meanwhile; a newer preview is on its way
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    showError(data?.detail || `Couldn't create the PDF (error ${res.status}).`);
    return;
  }
  const blob = await res.blob();
  if (id !== requestId) return;
  const match = /filename\*=UTF-8''([^;]+)/.exec(res.headers.get('Content-Disposition') || '');
  if (match) fileName = decodeURIComponent(match[1]);

  if (pdfUrl) URL.revokeObjectURL(pdfUrl);
  pdfUrl = URL.createObjectURL(blob);
  $('preview').src = pdfUrl;
  $('preview').hidden = false;
  $('preview-status').hidden = true;
  $('open-preview').href = pdfUrl;
  $('open-preview').hidden = false;
  $('export-info').textContent = `${(blob.size / 1024).toFixed(0)} KB`;
  setBusy(false);
}

function showError(message) {
  setBusy(false);
  $('preview').hidden = true;
  $('preview-status').hidden = false;
  $('preview-status').replaceChildren(errorNotice("Couldn't create the PDF", message, makePdf));
}

const refresh = debounce(makePdf, 350);

function download() {
  if (!pdfUrl) return;
  const link = el('a', { href: pdfUrl, download: fileName });
  document.body.append(link);
  link.click();
  link.remove();
  $('export-info').textContent = `Saved as ${fileName} in your Downloads folder.`;
}

async function init() {
  setupThemeToggle($('theme-toggle'));
  $('back-link').href = `/notes/${noteId}`;

  let note;
  try {
    note = await api(`/api/notes/${noteId}`);
  } catch (err) {
    const missing = err.status === 404;
    $('load-error').replaceChildren(errorNotice(missing ? "This note doesn't exist" : "Couldn't open this note",
      missing ? 'It may have been deleted.' : err.message, missing ? null : () => location.reload()));
    return;
  }
  document.title = `Export ${note.title || 'Untitled note'} · Margin`;
  $('note-title').textContent = note.title || 'Untitled note';

  const blocks = note.content?.blocks || [];
  $('set-flashcards-row').hidden = !blocks.some(b => b.type === 'flashcards');
  if (!blocks.length) {
    // Nothing enhanced yet: the PDF contains the rough notes
    $('set-rough').checked = true;
    $('set-rough').disabled = true;
    $('set-toc').checked = false;
    $('set-toc').disabled = true;
    $('export-hint').textContent = 'This note has no enhanced notes yet, so the PDF contains your rough notes.';
    $('export-hint').hidden = false;
  }

  for (const id of ['set-toc', 'set-flashcards', 'set-rough']) $(id).addEventListener('change', refresh);
  $('download').addEventListener('click', download);
  $('export').hidden = false;
  makePdf();
}

init();
