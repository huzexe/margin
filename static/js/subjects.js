// Subjects: shared list, the subject dropdown with "+ Add subject…", and the inline name form.

import { api } from './api.js';
import { el } from './ui.js';

const ADD = '__add__';
let subjects = [];
const listeners = new Set();

export function getSubjects() {
  return subjects;
}

export function onSubjectsChange(fn) {
  listeners.add(fn);
}

export async function loadSubjects() {
  subjects = await api('/api/subjects');
  listeners.forEach(fn => fn(subjects));
  return subjects;
}

export async function addSubject(name) {
  const created = await api('/api/subjects', { method: 'POST', body: { name } });
  await loadSubjects();
  return created;
}

export async function renameSubject(id, name) {
  await api(`/api/subjects/${id}`, { method: 'PATCH', body: { name } });
  await loadSubjects();
}

export async function deleteSubject(id) {
  await api(`/api/subjects/${id}`, { method: 'DELETE' });
  await loadSubjects();
}

/**
 * Inline form with one text field. onSubmit(value) may throw an ApiError;
 * its message is shown under the field and the form stays open.
 */
export function nameForm({ value = '', placeholder = 'Subject name', submitLabel = 'Add', onSubmit, onClose }) {
  const input = el('input', {
    class: 'input', name: 'name', maxlength: 60, placeholder,
    'aria-label': placeholder, autocomplete: 'off', value,
  });
  const error = el('div', { class: 'field-error', hidden: true });
  const submit = el('button', { class: 'btn btn-primary btn-sm', type: 'submit' }, submitLabel);
  const form = el('form', { class: 'add-subject' },
    el('div', { class: 'add-subject-row' },
      input,
      submit,
      el('button', { class: 'btn btn-ghost btn-sm', type: 'button', onclick: () => onClose() }, 'Cancel'),
    ),
    error,
  );

  const showError = message => { error.textContent = message; error.hidden = false; };
  input.addEventListener('input', () => { error.hidden = true; });
  input.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); onClose(); } });
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const name = input.value.trim().replace(/\s+/g, ' ');
    if (!name) return showError('Enter a subject name.');
    submit.disabled = true;
    try {
      await onSubmit(name);
    } catch (err) {
      showError(err.message);
      submit.disabled = false;
      input.focus();
    }
  });

  queueMicrotask(() => { input.focus(); input.select(); });
  return form;
}

/**
 * Turns a <select> into the subject picker. The form for a new subject opens
 * below `container`. onChange(subjectId | null) fires when the user picks a subject.
 */
export function subjectPicker(select, container, onChange) {
  let current = null; // selected subject id or null

  function render() {
    select.replaceChildren(
      new Option('No subject', ''),
      ...subjects.map(s => new Option(s.name, String(s.id))),
      new Option('+ Add subject…', ADD),
    );
    if (current != null && !subjects.some(s => s.id === current)) current = null;
    select.value = current == null ? '' : String(current);
  }

  function openForm() {
    if (container.querySelector('.add-subject')) return;
    const form = nameForm({
      onSubmit: async name => {
        const created = await addSubject(name);
        current = created.id;
        render();
        form.remove();
        onChange(current);
      },
      onClose: () => { form.remove(); select.focus(); },
    });
    container.append(form);
  }

  select.addEventListener('change', () => {
    if (select.value === ADD) {
      select.value = current == null ? '' : String(current);
      openForm();
      return;
    }
    current = select.value === '' ? null : Number(select.value);
    onChange(current);
  });

  onSubjectsChange(render);
  render();

  return {
    set(id) { current = id ?? null; render(); },
  };
}
