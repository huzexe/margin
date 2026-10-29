// Library page: subjects sidebar, search, sort and the note list.

import { api } from './api.js';
import { debounce, el, errorNotice, formatDate, icon, setupThemeToggle, toast } from './ui.js';
import {
  deleteSubject, getSubjects, loadSubjects, nameForm, onSubjectsChange, renameSubject, addSubject,
} from './subjects.js';

const listArea = document.getElementById('list-area');
const subjectList = document.getElementById('subject-list');
const searchInput = document.getElementById('search');
const sortSelect = document.getElementById('sort');
const heading = document.getElementById('list-heading');

// Filters live in the URL so Back from a note returns to the same view
const params = new URLSearchParams(location.search);
const state = {
  subjectId: params.has('subject') ? Number(params.get('subject')) : null,
  q: params.get('q') || '',
  sort: ['updated', 'created', 'title'].includes(params.get('sort')) ? params.get('sort') : 'updated',
  tag: params.get('tag') || null,
};
let tags = [];
let editing = null; // { id, mode: 'rename' | 'delete' } for the sidebar row being changed
let requestId = 0;

function syncUrl() {
  const p = new URLSearchParams();
  if (state.subjectId != null) p.set('subject', state.subjectId);
  if (state.q) p.set('q', state.q);
  if (state.sort !== 'updated') p.set('sort', state.sort);
  if (state.tag) p.set('tag', state.tag);
  history.replaceState(null, '', p.toString() ? `/?${p}` : '/');
}

/* ---------- Sidebar ---------- */

function renderSidebar() {
  const subjects = getSubjects();
  if (state.subjectId != null && !subjects.some(s => s.id === state.subjectId)) {
    state.subjectId = null;
    syncUrl();
  }

  const all = el('li', {}, el('a', {
    href: '/', 'aria-current': state.subjectId == null ? 'true' : false,
    onclick: e => { e.preventDefault(); selectSubject(null); },
  }, 'All notes'));

  const rows = subjects.map(s => {
    if (editing?.id === s.id && editing.mode === 'rename') {
      return el('li', {}, nameForm({
        value: s.name, submitLabel: 'Save', placeholder: 'Subject name',
        onSubmit: async name => { await renameSubject(s.id, name); editing = null; renderSidebar(); renderList(); },
        onClose: () => { editing = null; renderSidebar(); },
      }));
    }
    if (editing?.id === s.id && editing.mode === 'delete') {
      const count = s.note_count === 1 ? '1 note' : `${s.note_count} notes`;
      return el('li', { class: 'confirm-inline' },
        el('p', {}, `Delete “${s.name}”? `, s.note_count ? `Its ${count} will be kept under No subject.` : ''),
        el('div', { class: 'confirm-actions' },
          el('button', { class: 'btn btn-danger btn-sm', type: 'button', onclick: async () => {
            try {
              await deleteSubject(s.id);
              editing = null;
              renderSidebar();
              renderList();
            } catch (err) { toast(err.message, { error: true }); }
          } }, 'Delete'),
          el('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => { editing = null; renderSidebar(); } }, 'Cancel'),
        ),
      );
    }
    return el('li', { class: 'subject-item' },
      el('a', {
        href: `/?subject=${s.id}`, 'aria-current': state.subjectId === s.id ? 'true' : false,
        onclick: e => { e.preventDefault(); selectSubject(s.id); },
      }, el('span', { class: 'subject-name' }, s.name), el('span', { class: 'count' }, s.note_count)),
      el('span', { class: 'subject-actions' },
        el('button', {
          class: 'btn btn-ghost btn-icon btn-sm', type: 'button', title: 'Rename', 'aria-label': `Rename ${s.name}`,
          html: icon('pencil'), onclick: () => { editing = { id: s.id, mode: 'rename' }; renderSidebar(); },
        }),
        el('button', {
          class: 'btn btn-ghost btn-icon btn-sm', type: 'button', title: 'Delete', 'aria-label': `Delete ${s.name}`,
          html: icon('trash'), onclick: () => { editing = { id: s.id, mode: 'delete' }; renderSidebar(); },
        }),
      ),
    );
  });

  subjectList.replaceChildren(all, ...rows);
  document.getElementById('subjects-empty').hidden = subjects.length > 0;
  updateHeading();
}

function updateHeading() {
  const current = getSubjects().find(s => s.id === state.subjectId);
  heading.textContent = [current ? current.name : 'All notes', state.tag ? `#${state.tag}` : null]
    .filter(Boolean).join(' · ');
}

async function loadTags() {
  try { tags = await api('/api/tags'); } catch { tags = []; }
  if (state.tag && !tags.some(t => t.name.toLowerCase() === state.tag.toLowerCase())) {
    state.tag = null;
    syncUrl();
  }
  renderTags();
}

function renderTags() {
  const box = document.getElementById('tag-list');
  document.getElementById('tags-section').hidden = !tags.length;
  box.replaceChildren(...tags.map(t => el('button', {
    type: 'button', class: 'tag-filter', 'aria-pressed': String(state.tag === t.name),
    title: `${t.note_count} ${t.note_count === 1 ? 'note' : 'notes'}`,
    onclick: () => {
      state.tag = state.tag === t.name ? null : t.name; // click again to clear
      syncUrl(); renderTags(); updateHeading(); renderList();
    },
  }, `#${t.name}`)));
}

function selectSubject(id) {
  state.subjectId = id;
  syncUrl();
  renderSidebar();
  renderList();
}

const addButton = document.getElementById('add-subject');
addButton.addEventListener('click', () => {
  const wrap = document.getElementById('sidebar-add');
  if (wrap.querySelector('form')) return;
  addButton.hidden = true;
  const close = () => { form.remove(); addButton.hidden = false; addButton.focus(); };
  const form = nameForm({ onSubmit: async name => { await addSubject(name); close(); }, onClose: close });
  wrap.append(form);
});

/* ---------- Note list ---------- */

function emptyState(title, text, withButton) {
  return el('div', { class: 'empty-state' },
    el('h3', {}, title),
    text && el('p', {}, text),
    withButton && el('a', { class: 'btn btn-primary', href: newNoteHref() }, 'New note'),
  );
}

function newNoteHref() {
  return state.subjectId != null ? `/notes/new?subject=${state.subjectId}` : '/notes/new';
}

async function renderList() {
  const id = ++requestId;
  const p = new URLSearchParams({ sort: state.sort });
  if (state.q) p.set('q', state.q);
  if (state.subjectId != null) p.set('subject_id', state.subjectId);
  if (state.tag) p.set('tag', state.tag);

  let notes;
  try {
    notes = await api(`/api/notes?${p}`);
  } catch (err) {
    if (id !== requestId) return;
    listArea.replaceChildren(errorNotice("Couldn't load notes", err.message, renderList));
    return;
  }
  if (id !== requestId) return; // a newer search finished first

  document.getElementById('new-note').href = newNoteHref();

  if (!notes.length) {
    const subject = getSubjects().find(s => s.id === state.subjectId);
    if (state.q) listArea.replaceChildren(emptyState(`No notes match “${state.q}”`, 'Try fewer or different words.'));
    else if (state.tag) listArea.replaceChildren(emptyState(`No notes tagged #${state.tag} here`, null));
    else if (subject) listArea.replaceChildren(emptyState(`No notes in ${subject.name} yet`, null, true));
    else listArea.replaceChildren(emptyState('No notes yet', 'Create a note, type what you hear in class, and keep everything organized by subject.', true));
    return;
  }

  listArea.replaceChildren(el('ul', { class: 'note-list' }, ...notes.map(n => el('li', {},
    el('a', { class: 'note-row', href: `/notes/${n.id}` },
      el('span', { class: 'note-row-main' },
        el('span', { class: 'note-row-title' + (n.title ? '' : ' is-untitled') }, n.title || 'Untitled note'),
        n.topic && el('span', { class: 'note-row-topic' }, n.topic),
        n.tags?.length ? el('span', { class: 'note-row-tags' }, ...n.tags.map(t => el('span', {}, `#${t}`))) : null,
      ),
      n.subject_name && state.subjectId == null ? el('span', { class: 'subject-chip' }, n.subject_name) : null,
      el('time', { class: 'note-row-date', datetime: n.updated_at, title: `Last edited ${new Date(n.updated_at).toLocaleString()}` }, formatDate(n.updated_at)),
    ),
  ))));
}

/* ---------- Wiring ---------- */

searchInput.value = state.q;
sortSelect.value = state.sort;

searchInput.addEventListener('input', debounce(() => {
  state.q = searchInput.value.trim();
  syncUrl();
  renderList();
}, 250));

sortSelect.addEventListener('change', () => {
  state.sort = sortSelect.value;
  syncUrl();
  renderList();
});

document.addEventListener('keydown', e => {
  if (e.key === '/' && document.activeElement === document.body) {
    e.preventDefault();
    searchInput.focus();
  }
});

setupThemeToggle(document.getElementById('theme-toggle'));
onSubjectsChange(renderSidebar);

loadSubjects().catch(err => toast(err.message, { error: true }));
loadTags();
renderList();

// Coming back with the browser's Back button can show a cached page; refresh the data
addEventListener('pageshow', e => {
  if (e.persisted) { loadSubjects().catch(() => {}); loadTags(); renderList(); }
});
