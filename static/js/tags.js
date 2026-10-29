// Tag field: chips plus a text box. Enter or comma adds a tag; Backspace in the empty box removes the last.

import { api } from './api.js';
import { el } from './ui.js';

const MAX_TAG = 30;
const MAX_TAGS = 20;

function clean(text) {
  return text.replace(/,/g, ' ').replace(/\s+/g, ' ').trim().replace(/^#+/, '').trim();
}

/**
 * box: container (chips are drawn inside it, before the input)
 * input: the text box; datalist: suggestions from existing tags
 * onChange(tags) is called after every add/remove.
 */
export function createTagEditor({ box, input, datalist, error, onChange }) {
  let tags = [];

  function draw() {
    box.querySelectorAll('.tag-chip').forEach(c => c.remove());
    for (const tag of tags) {
      box.insertBefore(el('span', { class: 'tag-chip' },
        el('span', {}, `#${tag}`),
        el('button', {
          type: 'button', class: 'tag-remove', 'aria-label': `Remove tag ${tag}`, title: 'Remove',
          onclick: () => { remove(tag); input.focus(); },
        }, '×'),
      ), input);
    }
    input.placeholder = tags.length ? '' : 'Add a tag…';
  }

  function showError(message) {
    error.textContent = message;
    error.hidden = !message;
  }

  function add(text) {
    const name = clean(text);
    if (!name) return;
    if (name.length > MAX_TAG) return showError(`Tags can be at most ${MAX_TAG} characters.`);
    if (tags.some(t => t.toLowerCase() === name.toLowerCase())) return showError('');
    if (tags.length >= MAX_TAGS) return showError(`A note can have at most ${MAX_TAGS} tags.`);
    showError('');
    tags = [...tags, name].sort((a, b) => a.localeCompare(b, undefined, { sensitivity: 'base' }));
    draw();
    onChange(tags);
  }

  function remove(name) {
    tags = tags.filter(t => t !== name);
    draw();
    onChange(tags);
  }

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      add(input.value);
      input.value = '';
    } else if (e.key === 'Backspace' && !input.value && tags.length) {
      remove(tags.at(-1));
    }
  });
  // Picking a suggestion from the list, or leaving the box with text in it, adds the tag
  input.addEventListener('change', () => { if (input.value.trim()) { add(input.value); input.value = ''; } });
  box.addEventListener('click', e => { if (e.target === box) input.focus(); });

  async function loadSuggestions() {
    try {
      const all = await api('/api/tags');
      datalist.replaceChildren(...all.map(t => el('option', { value: t.name })));
    } catch { /* suggestions are optional */ }
  }
  input.addEventListener('focus', loadSuggestions, { once: true });

  return {
    get: () => tags,
    set(list) { tags = [...list]; draw(); },
  };
}
