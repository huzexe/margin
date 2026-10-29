// Note page: details, rough notes and enhanced notes. Everything saves automatically.

import { api, ApiError } from './api.js';
import { repairDiagrams } from './diagrams.js';
import { createEditor } from './editor.js';
import { setupSectionTools } from './sections.js';
import { debounce, el, errorNotice, setupThemeToggle, toast } from './ui.js';
import { loadSubjects, subjectPicker } from './subjects.js';
import { createTagEditor } from './tags.js';

const MAX_ROUGH = 20000;
const FIELDS = ['title', 'topic', 'subject_id', 'rough_text', 'tags'];
const DETAIL_LABEL = { concise: 'Concise', standard: 'Standard', detailed: 'Detailed' };

const $ = id => document.getElementById(id);
const titleInput = $('title');
const topicInput = $('topic');
const roughInput = $('rough');
const statusEl = $('save-status');
const enhanceButton = $('enhance');

const match = location.pathname.match(/^\/notes\/(\d+)$/);
const state = {
  id: match ? Number(match[1]) : null,
  saved: { title: '', topic: '', subject_id: null, rough_text: '', tags: [] }, // what the server has
  subjectId: null,
  extra: {},            // other changes waiting to be saved (enhanced notes, options…)
  saving: false,
  again: false,
  failed: false,
  hasContent: false,    // enhanced notes exist
  contentEdited: false, // user changed them after the last enhance
  options: null,        // options used for the last enhance
  working: null,        // AbortController while enhancing
};
let editor = null;
let tagEditor = null;
let retryTimer;

/* ---------- Saving ---------- */

function values() {
  return {
    title: titleInput.value,
    topic: topicInput.value,
    subject_id: state.subjectId,
    rough_text: roughInput.value,
    tags: tagEditor ? tagEditor.get() : [],
  };
}

const same = (a, b) => (Array.isArray(a) ? JSON.stringify(a) === JSON.stringify(b) : a === b);

function changes() {
  const now = values();
  const diff = Object.fromEntries(FIELDS.filter(f => !same(now[f], state.saved[f])).map(f => [f, now[f]]));
  return { ...diff, ...state.extra };
}

function isBlank(v) {
  return !v.title.trim() && !v.topic.trim() && !v.rough_text.trim() && v.subject_id == null && !v.tags.length;
}

function setStatus(kind, message) {
  statusEl.className = 'save-status' + (kind === 'error' ? ' is-error' : '');
  if (kind === 'error') {
    statusEl.replaceChildren(
      el('span', { title: message }, 'Not saved'),
      el('button', { class: 'link-button', type: 'button', onclick: () => save() }, 'Retry'),
    );
  } else {
    statusEl.textContent = { saving: 'Saving…', saved: 'Saved', unsaved: 'Unsaved changes', '': '' }[kind];
  }
}

async function save() {
  clearTimeout(retryTimer);
  scheduleSave.cancel();
  if (state.saving) { state.again = true; return; }

  const diff = changes();
  if (!Object.keys(diff).length) { if (!state.failed) setStatus(state.id ? 'saved' : ''); return; }
  if (state.id == null && isBlank(values())) return; // don't create empty notes

  const sentExtra = state.extra;
  state.saving = true;
  setStatus('saving');
  try {
    if (state.id == null) {
      const sent = values();
      const note = await api('/api/notes', { method: 'POST', body: sent });
      state.id = note.id;
      state.saved = sent;
      history.replaceState(null, '', `/notes/${note.id}`);
      $('delete-note').hidden = false;
    } else {
      await api(`/api/notes/${state.id}`, { method: 'PATCH', body: diff });
      for (const f of FIELDS) if (f in diff) state.saved[f] = diff[f];
      // keep any extra changes that were made while this save was running
      if (state.extra === sentExtra) state.extra = {};
    }
    state.failed = false;
  } catch (err) {
    state.failed = true;
    setStatus('error', err.message);
    if (err.status === 404) {
      toast('This note was deleted in another tab. Your text is still on screen; copy it if you need it.', { error: true });
    } else if (err.status === 422) {
      toast(err.message, { error: true });
    } else {
      retryTimer = setTimeout(save, 5000); // connection problem: try again shortly
    }
  } finally {
    state.saving = false;
  }

  if (state.again) { state.again = false; return save(); }
  if (!state.failed) setStatus(Object.keys(changes()).length ? 'unsaved' : 'saved');
}

const scheduleSave = debounce(save, 700);

function onEdit() {
  if (!state.failed) setStatus('unsaved');
  scheduleSave();
}

// Wait until everything typed so far is on the server
async function saveNow() {
  await save();
  while (state.saving) await new Promise(r => setTimeout(r, 50));
  if (Object.keys(changes()).length) await save();
  return !state.failed;
}

// When the tab is hidden or closed, send any unsaved changes right away
function flush() {
  const diff = changes();
  if (!Object.keys(diff).length || state.saving) return;
  if (state.id != null) {
    api(`/api/notes/${state.id}`, { method: 'PATCH', body: diff, keepalive: true })
      .then(() => { for (const f of FIELDS) if (f in diff) state.saved[f] = diff[f]; state.extra = {}; })
      .catch(() => {});
  } else if (!isBlank(values())) {
    save();
  }
}

/* ---------- Options ---------- */

function readOptions() {
  return {
    simplify: $('opt-simplify').checked,
    diagrams: $('opt-diagrams').checked,
    flashcards: $('opt-flashcards').checked,
    applications: $('opt-applications').checked,
    detail: $('opt-detail').querySelector('[aria-pressed="true"]').dataset.value,
  };
}

function writeOptions(o) {
  $('opt-simplify').checked = Boolean(o?.simplify);
  $('opt-diagrams').checked = Boolean(o?.diagrams);
  $('opt-flashcards').checked = Boolean(o?.flashcards);
  $('opt-applications').checked = Boolean(o?.applications);
  setDetail(o?.detail || 'standard');
}

function setDetail(value) {
  for (const b of $('opt-detail').querySelectorAll('button')) {
    b.setAttribute('aria-pressed', String(b.dataset.value === value));
  }
}

/* ---------- Enhanced pane ---------- */

const PANELS = ['enh-empty', 'enh-working', 'enh-message', 'editor-holder'];

function showPanel(id) {
  for (const p of PANELS) $(p).hidden = p !== id;
  $('enh-progress').hidden = id !== 'enh-working';
}

function showEditorOrEmpty() {
  showPanel(state.hasContent ? 'editor-holder' : 'enh-empty');
}

function updateEnhancedMeta() {
  const parts = [];
  if (state.hasContent && state.options) parts.push(DETAIL_LABEL[state.options.detail] || '');
  if (state.hasContent && state.contentEdited) parts.push('edited');
  $('enhanced-meta').textContent = parts.filter(Boolean).join(' · ');
}

function updateEnhanceButton() {
  const hasRough = Boolean(roughInput.value.trim());
  enhanceButton.disabled = Boolean(state.working) || !hasRough;
  enhanceButton.title = hasRough ? 'Enhance notes (Ctrl+Enter)' : 'Write some rough notes first';
  const canExport = hasRough || state.hasContent;
  $('export').disabled = Boolean(state.working) || !canExport;
  $('export').title = canExport ? 'Preview and download as PDF' : 'Write something first';
}

async function openExport() {
  if (!(await saveNow()) || state.id == null) {
    toast("Your latest changes couldn't be saved, so the PDF would be out of date. Try again in a moment.", { error: true });
    return;
  }
  location.href = `/notes/${state.id}/export`;
}

// A question with buttons, shown inside the enhanced pane
function ask(text, confirmLabel) {
  return new Promise(resolve => {
    const done = answer => { showEditorOrEmpty(); resolve(answer); };
    const yes = el('button', { class: 'btn btn-primary btn-sm', type: 'button', onclick: () => done(true) }, confirmLabel);
    $('enh-message').replaceChildren(el('div', { class: 'confirm-panel', role: 'alertdialog' },
      el('p', {}, text),
      el('div', { class: 'confirm-actions' },
        yes,
        el('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => done(false) }, 'Cancel'),
      ),
    ));
    showPanel('enh-message');
    showTab('enhanced');
    yes.focus();
  });
}

async function enhance({ force = false, skipEditCheck = false } = {}) {
  if (state.working || !roughInput.value.trim()) return;

  if (state.hasContent && state.contentEdited && !skipEditCheck) {
    const ok = await ask('Enhancing again will replace the enhanced notes, including the changes you made to them.', 'Replace');
    if (!ok) return;
  }

  if (!(await saveNow()) || state.id == null) {
    toast("Your notes couldn't be saved, so they can't be enhanced yet.", { error: true });
    return;
  }

  const options = readOptions();
  const controller = new AbortController();
  state.working = controller;
  updateEnhanceButton();
  enhanceButton.textContent = 'Enhancing…';
  showPanel('enh-working');
  showTab('enhanced');

  try {
    const result = await postJSON(`/api/notes/${state.id}/enhance`, { options, force }, controller.signal);
    await repairDiagrams(result.content.blocks, text => { $('enh-status').textContent = text; });
    if (controller.signal.aborted) throw new DOMException('Cancelled', 'AbortError');
    // What was there before, so the replacement can be undone
    const before = state.hasContent ? {
      content: await editor.getData(), options: state.options, edited: state.contentEdited, hash: state.sourceHash,
    } : null;
    await editor.setData(result.content);
    state.hasContent = true;
    state.contentEdited = false;
    state.options = result.options;
    state.sourceHash = result.source_hash;
    state.extra = { ...state.extra, content: result.content, options: result.options,
      source_hash: result.source_hash, content_edited: false };
    showPanel('editor-holder');
    updateEnhancedMeta();
    await save();
    if (before) {
      toast('Enhanced notes replaced.', { action: { label: 'Undo', onClick: async () => {
        await editor.setData(before.content);
        Object.assign(state, { options: before.options, contentEdited: before.edited, sourceHash: before.hash });
        writeOptions(before.options);
        state.extra = { ...state.extra, content: before.content, options: before.options,
          source_hash: before.hash ?? '', content_edited: before.edited };
        updateEnhancedMeta();
        await save();
        toast('Previous enhanced notes restored.');
      } } });
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      showEditorOrEmpty();
    } else if (err.status === 409) {
      finish();
      const again = await ask("Your notes and options haven't changed since they were last enhanced. Enhance again anyway?", 'Enhance again');
      if (again) return enhance({ force: true, skipEditCheck: true });
      return;
    } else {
      $('enh-message').replaceChildren(errorNotice("Couldn't enhance your notes", err.message,
        () => enhance({ force, skipEditCheck: true })));
      if (state.hasContent) {
        $('enh-message').append(el('button', { class: 'link-button enh-back', type: 'button', onclick: showEditorOrEmpty },
          'Back to your enhanced notes'));
      }
      showPanel('enh-message');
    }
  }
  finish();

  function finish() {
    state.working = null;
    enhanceButton.textContent = 'Enhance notes';
    $('enh-status').textContent = 'Enhancing your notes…';
    updateEnhanceButton();
  }
}

// Rewrite one section (called by the section Regenerate form)
async function regenerateSection({ ids, instruction, signal, setStatus }) {
  state.working = new AbortController(); // blocks a full Enhance meanwhile
  updateEnhanceButton();
  try {
    const data = await editor.getData();
    const blocks = data.blocks.filter(b => ids.includes(b.id));
    if (!blocks.length) throw new ApiError('This section is empty.', 422);
    await saveNow();
    const result = await postJSON(`/api/notes/${state.id}/regenerate-section`,
      { blocks, instruction, options: readOptions() }, signal);
    await repairDiagrams(result.blocks, setStatus);
    if (signal.aborted) throw new DOMException('Cancelled', 'AbortError');
    const { content, ids: newIds } = await editor.replaceBlocks(ids, result.blocks);
    const wasEdited = state.contentEdited;
    state.contentEdited = true;
    state.extra = { ...state.extra, content, content_edited: true };
    updateEnhancedMeta();
    await save();
    toast('Section updated.', { action: { label: 'Undo', onClick: async () => {
      const { content: restored } = await editor.replaceBlocks(newIds, blocks);
      state.contentEdited = wasEdited;
      state.extra = { ...state.extra, content: restored, content_edited: wasEdited };
      updateEnhancedMeta();
      await save();
      toast('Section restored.');
    } } });
  } finally {
    state.working = null;
    updateEnhanceButton();
  }
}

async function postJSON(path, body, signal) {
  let res;
  try {
    res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError("Can't reach Margin. Check that the app is still running in the terminal.", 0);
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(data?.detail || `Something went wrong (error ${res.status}).`, res.status);
  return data;
}

const onEditorChange = debounce(data => {
  state.contentEdited = true;
  state.extra = { ...state.extra, content: data, content_edited: true };
  updateEnhancedMeta();
  onEdit();
}, 600);

/* ---------- Layout ---------- */

function showTab(tab) {
  $('workspace').dataset.tab = tab;
  for (const b of $('pane-tabs').querySelectorAll('button')) {
    b.setAttribute('aria-pressed', String(b.dataset.tab === tab));
  }
}

function updateCount() {
  const text = roughInput.value;
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  $('rough-count').textContent = text.length > MAX_ROUGH * 0.8
    ? `${text.length.toLocaleString()} / ${MAX_ROUGH.toLocaleString()} characters`
    : `${words.toLocaleString()} ${words === 1 ? 'word' : 'words'}`;
  $('rough-count').classList.toggle('is-warning', text.length > MAX_ROUGH * 0.95);
}

function updateTitle() {
  document.title = `${titleInput.value.trim() || 'Untitled note'} · Margin`;
}

/* ---------- Start ---------- */

async function init() {
  setupThemeToggle($('theme-toggle'));

  // Return to the library view the user came from (keeps subject filter / search)
  if (document.referrer) {
    const ref = new URL(document.referrer);
    if (ref.origin === location.origin && ref.pathname === '/') {
      $('back-link').href = ref.pathname + ref.search;
      $('library-link').href = ref.pathname + ref.search;
    }
  }

  let note = null;
  let defaults = null;
  try {
    const [, loaded, settings] = await Promise.all([
      loadSubjects(),
      state.id != null ? api(`/api/notes/${state.id}`) : null,
      api('/api/settings').catch(() => null), // defaults are optional; the page works without them
    ]);
    note = loaded;
    defaults = settings?.default_options ?? null;
  } catch (err) {
    const title = err.status === 404 ? "This note doesn't exist" : "Couldn't open this note";
    const message = err.status === 404 ? 'It may have been deleted.' : err.message;
    $('load-error').replaceChildren(
      errorNotice(title, message, err.status === 404 ? null : () => location.reload()),
      el('p', { class: 'load-error-back' }, el('a', { href: '/' }, 'Back to library')),
    );
    return;
  }

  const picker = subjectPicker($('subject'), $('subject-field'), id => {
    state.subjectId = id;
    save();
  });
  tagEditor = createTagEditor({
    box: $('tag-box'), input: $('tag-input'), datalist: $('tag-suggestions'), error: $('tag-error'),
    onChange: () => save(),
  });

  if (note) {
    titleInput.value = note.title;
    topicInput.value = note.topic;
    roughInput.value = note.rough_text;
    tagEditor.set(note.tags);
    state.subjectId = note.subject_id;
    state.saved = { title: note.title, topic: note.topic, subject_id: note.subject_id,
      rough_text: note.rough_text, tags: [...note.tags] };
    state.hasContent = Boolean(note.content?.blocks?.length);
    state.contentEdited = note.content_edited;
    state.options = note.options;
    state.sourceHash = note.source_hash;
    writeOptions(note.options ?? defaults); // never enhanced: start from the default options
    $('delete-note').hidden = false;
    setStatus('saved');
  } else {
    // New note opened from a subject in the library starts in that subject (not saved until you type)
    const fromSubject = Number(new URLSearchParams(location.search).get('subject'));
    if (fromSubject) state.subjectId = fromSubject;
    writeOptions(defaults);
  }
  picker.set(state.subjectId);
  // The picker drops ids that no longer exist, so read back what it actually shows
  state.subjectId = $('subject').value ? Number($('subject').value) : null;
  state.saved.subject_id = note ? note.subject_id : state.subjectId;

  // Listen before the fields appear, so nothing typed while the editor loads is missed
  titleInput.addEventListener('input', () => { updateTitle(); onEdit(); });
  topicInput.addEventListener('input', onEdit);
  roughInput.addEventListener('input', () => { updateCount(); updateEnhanceButton(); onEdit(); });
  titleInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') { e.preventDefault(); roughInput.focus(); }
  });

  $('note').hidden = false;
  updateTitle();
  updateCount();
  updateEnhanceButton();
  updateEnhancedMeta();
  if (state.hasContent) showTab('enhanced');

  try {
    editor = await createEditor($('editor-holder'), {
      data: state.hasContent ? note.content : { blocks: [] },
      onChange: onEditorChange,
    });
  } catch (err) {
    console.error(err);
    $('enh-message').replaceChildren(errorNotice("Couldn't start the editor", 'Reload the page to try again.', () => location.reload()));
    showPanel('enh-message');
    enhanceButton.disabled = true;
    return;
  }
  showEditorOrEmpty();
  setupSectionTools({
    pane: $('pane-enhanced'),
    holder: $('editor-holder'),
    editor,
    isBusy: () => Boolean(state.working),
    onRegenerate: regenerateSection,
  });
  (note ? roughInput : titleInput).focus();

  $('opt-detail').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (b) setDetail(b.dataset.value);
  });
  $('pane-tabs').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (b) showTab(b.dataset.tab);
  });

  enhanceButton.addEventListener('click', () => enhance());
  $('export').addEventListener('click', openExport);
  $('enh-cancel').addEventListener('click', () => state.working?.abort());

  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); enhance(); }
  });

  document.addEventListener('visibilitychange', () => { if (document.hidden) flush(); });
  window.addEventListener('pagehide', flush);
  window.addEventListener('beforeunload', e => {
    if (state.working || (state.failed && Object.keys(changes()).length)) e.preventDefault();
  });

  // Delete with an inline confirmation
  const confirmBar = $('delete-confirm');
  $('delete-note').addEventListener('click', () => { confirmBar.hidden = false; $('delete-no').focus(); });
  $('delete-no').addEventListener('click', () => { confirmBar.hidden = true; });
  $('delete-yes').addEventListener('click', async () => {
    $('delete-yes').disabled = true;
    try {
      scheduleSave.cancel();
      clearTimeout(retryTimer);
      await api(`/api/notes/${state.id}`, { method: 'DELETE' });
      state.saved = values(); // nothing left to save
      state.extra = {};
      location.href = $('back-link').getAttribute('href');
    } catch (err) {
      $('delete-yes').disabled = false;
      toast(err.message, { error: true });
    }
  });
}

init();
