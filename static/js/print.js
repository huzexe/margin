// Print view of a note, used to make the PDF. Renders the saved enhanced notes as plain HTML
// (no editor), draws formulas and diagrams, then sets window.__printReady = true.
// Settings come from the URL: toc, flashcards, rough (1/0), size, margins.

import { api } from './api.js';
import { renderDiagram, diagramOutline } from './diagrams.js';
import { sanitize } from './blocks/sanitize.js';
import { el } from './ui.js';

const params = new URLSearchParams(location.search);
const settings = {
  toc: params.get('toc') !== '0',
  flashcards: params.get('flashcards') !== '0',
  rough: params.get('rough') === '1',
  size: ['small', 'medium', 'large'].includes(params.get('size')) ? params.get('size') : 'medium',
};
const CALLOUT_LABEL = { definition: 'Definition', example: 'Example', takeaway: 'Key takeaways', verify: 'Please verify' };

// Inline HTML from the editor: keep simple formatting only (links become plain text)
function html(value) {
  const span = el('span');
  span.innerHTML = sanitize(value || '');
  return span;
}

function listEl(items, ordered) {
  const list = el(ordered ? 'ol' : 'ul');
  for (const item of items || []) {
    const content = typeof item === 'string' ? item : item.content;
    const li = el('li', {}, html(content));
    if (item.items?.length) li.append(listEl(item.items, ordered));
    list.append(li);
  }
  return list;
}

const pendingDiagrams = [];
let heading = ''; // heading of the section being rendered

function block(b) {
  const d = b.data || {};
  switch (b.type) {
    case 'paragraph': return el('p', {}, html(d.text));
    case 'header': return el(d.level === 3 ? 'h3' : 'h2', {}, html(d.text));
    case 'list': return listEl(d.items, d.style === 'ordered');
    case 'callout': {
      const body = el('div', { class: 'callout-body' });
      body.innerHTML = sanitize(d.text || '');
      // Under a "Key takeaways" heading the box label would just repeat it
      const label = d.kind === 'takeaway' && heading === 'Key takeaways' ? null
        : el('span', { class: 'callout-label' }, CALLOUT_LABEL[d.kind] || 'Note');
      return el('div', { class: `callout callout-${d.kind || 'definition'}` }, label, body);
    }
    case 'formula': {
      const math = el('div', { class: 'formula-display' });
      try {
        window.katex.render(d.latex || '', math, { displayMode: true, throwOnError: false, strict: false });
      } catch { math.textContent = d.latex || ''; }
      return el('div', { class: 'callout callout-formula' },
        el('span', { class: 'callout-label' }, 'Formula'), math,
        d.text ? el('div', { class: 'formula-text' }, html(d.text)) : null);
    }
    case 'code': return el('pre', {}, el('code', {}, d.code || ''));
    case 'table': {
      const rows = d.content || [];
      const table = el('table');
      const start = d.withHeadings && rows.length ? 1 : 0;
      if (start) table.append(el('thead', {}, el('tr', {}, ...rows[0].map(c => el('th', {}, html(c))))));
      table.append(el('tbody', {}, ...rows.slice(start).map(r => el('tr', {}, ...r.map(c => el('td', {}, html(c)))))));
      return table;
    }
    case 'diagram': {
      const canvas = el('div', { class: 'diagram-canvas' });
      pendingDiagrams.push({ canvas, code: d.code || '' });
      return el('figure', { class: 'diagram' }, canvas, d.caption ? el('figcaption', {}, d.caption) : null);
    }
    case 'flashcards': return flashcards(d.cards || []);
    default: return null;
  }
}

function flashcards(cards) {
  return el('ol', { class: 'cards' }, ...cards.map(c => el('li', { class: 'card' },
    el('div', { class: 'card-q' }, html(c.question)),
    el('div', { class: 'card-a' }, html(c.answer)))));
}

// Split blocks into sections at each level-2 heading
function sections(blocks) {
  const out = [];
  for (const b of blocks) {
    if (b.type === 'header' && b.data?.level !== 3) out.push({ heading: b, blocks: [] });
    else if (out.length) out.at(-1).blocks.push(b);
    else out.push({ heading: null, blocks: [b] });
  }
  return out;
}

function plain(htmlText) {
  const span = el('span');
  span.innerHTML = sanitize(htmlText || '');
  return span.textContent.trim();
}

async function main() {
  const id = Number(location.pathname.match(/^\/notes\/(\d+)\/print$/)?.[1]);
  const note = await api(`/api/notes/${id}`);
  document.title = note.title || 'Untitled note';
  document.documentElement.dataset.size = settings.size;
  const doc = document.getElementById('doc');

  // Title block
  const meta = [note.subject_name, note.topic].filter(Boolean).join(' · ');
  const date = new Date(note.updated_at).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
  const titleBlock = el('header', { class: 'title-block' },
    el('h1', {}, note.title || 'Untitled note'),
    el('p', { class: 'meta' }, [meta, date].filter(Boolean).join(' · ')));

  const all = sections(note.content?.blocks || []);
  const cardSections = all.filter(s => s.blocks.some(b => b.type === 'flashcards'));
  const body = all.filter(s => !cardSections.includes(s));
  const parts = []; // { id, title, el }

  body.forEach((s, i) => {
    const sec = el('section', { class: 'section', id: `s${i}` });
    heading = s.heading ? plain(s.heading.data.text) : '';
    if (s.heading) sec.append(block(s.heading));
    for (const b of s.blocks) { const node = block(b); if (node) sec.append(node); }
    parts.push({ id: sec.id, title: s.heading ? plain(s.heading.data.text) : null, el: sec });
  });

  if (settings.flashcards && cardSections.length) {
    const sec = el('section', { class: 'section section-cards', id: 'cards' }, el('h2', {}, 'Flashcards'));
    for (const s of cardSections) for (const b of s.blocks) { const node = block(b); if (node) sec.append(node); }
    parts.push({ id: sec.id, title: 'Flashcards', el: sec });
  }

  const noContent = !body.length;
  if ((settings.rough || noContent) && note.rough_text.trim()) {
    const sec = el('section', { class: 'section' + (noContent ? '' : ' section-rough'), id: 'rough' },
      el('h2', {}, noContent ? 'Notes' : 'Original rough notes'),
      el('div', { class: 'rough' }, note.rough_text));
    parts.push({ id: sec.id, title: noContent ? 'Notes' : 'Original rough notes', el: sec });
  }

  // Table of contents: page numbers are filled in by the server after a first print
  const tocItems = parts.filter(p => p.title);
  const toc = el('nav', { class: 'toc', 'aria-label': 'Contents' }, el('h2', { class: 'toc-title' }, 'Contents'),
    el('ol', {}, ...tocItems.map(p => el('li', {},
      el('a', { href: `#${p.id}` }, p.title), el('span', { class: 'dots' }), el('span', { class: 'toc-page' }, '')))));
  const useToc = settings.toc && tocItems.length > 1;
  const front = el('div', { class: 'front' + (useToc ? ' front-break' : '') }, titleBlock, useToc ? toc : null);

  doc.replaceChildren(front, ...parts.map(p => p.el));

  window.__tocHeadings = useToc ? tocItems.map(p => p.title) : [];
  window.__showToc = show => { toc.hidden = !show; };
  window.__setTocPages = pages => {
    toc.querySelectorAll('.toc-page').forEach((span, i) => { span.textContent = pages[i] ?? ''; });
  };

  for (const { canvas, code } of pendingDiagrams) {
    try {
      canvas.innerHTML = await renderDiagram(code);
    } catch {
      const points = diagramOutline(code);
      canvas.replaceChildren(el('p', { class: 'diagram-note' }, 'Diagram (main points):'),
        points.length ? el('ul', {}, ...points.map(p => el('li', {}, p))) : el('p', {}, '—'));
    }
  }
  await document.fonts.ready;
}

main().then(
  () => { window.__printReady = true; },
  err => { window.__printReady = err?.message || "Couldn't prepare this note for printing."; },
);
