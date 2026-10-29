// Full-screen view for a diagram: zoom in/out, fit to screen, scroll to move around. Esc closes.

import { el } from './ui.js';

const STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3, 4];

export function openZoom(svgMarkup, caption) {
  const stage = el('div', { class: 'zoom-stage', tabindex: 0 });
  stage.innerHTML = svgMarkup;
  const svg = stage.querySelector('svg');
  if (!svg) return;

  // Natural size from the diagram's own coordinates
  const box = svg.viewBox?.baseVal;
  const natural = box && box.width ? { w: box.width, h: box.height } : { w: 800, h: 600 };
  svg.removeAttribute('style');
  svg.removeAttribute('height');

  const label = el('span', { class: 'zoom-level', 'aria-live': 'polite' });
  let scale = 1;

  function apply(next) {
    scale = Math.min(4, Math.max(0.25, next));
    svg.setAttribute('width', String(Math.round(natural.w * scale)));
    svg.setAttribute('height', String(Math.round(natural.h * scale)));
    label.textContent = `${Math.round(scale * 100)}%`;
  }
  function fit() {
    const w = stage.clientWidth - 48, h = stage.clientHeight - 48;
    apply(Math.min(w / natural.w, h / natural.h));
  }
  const step = dir => apply(dir > 0
    ? STEPS.find(s => s > scale + 0.01) ?? 4
    : [...STEPS].reverse().find(s => s < scale - 0.01) ?? 0.25);

  const button = (text, title, onClick) => el('button', { class: 'btn btn-sm', type: 'button', title, 'aria-label': title, onclick: onClick }, text);
  const dialog = el('dialog', { class: 'zoom-dialog', 'aria-label': caption || 'Diagram' },
    el('div', { class: 'zoom-bar' },
      el('span', { class: 'zoom-caption' }, caption || 'Diagram'),
      el('div', { class: 'zoom-controls' },
        button('−', 'Zoom out', () => step(-1)), label, button('+', 'Zoom in', () => step(1)),
        button('Fit', 'Fit to screen', fit), button('100%', 'Actual size', () => apply(1)),
        el('button', { class: 'btn btn-primary btn-sm', type: 'button', onclick: () => dialog.close() }, 'Close')),
    ),
    stage,
  );

  stage.addEventListener('wheel', e => {
    if (!e.ctrlKey) return; // plain wheel scrolls; Ctrl + wheel zooms
    e.preventDefault();
    step(e.deltaY < 0 ? 1 : -1);
  }, { passive: false });
  dialog.addEventListener('keydown', e => {
    if (e.key === '+' || e.key === '=') step(1);
    if (e.key === '-') step(-1);
    if (e.key === '0') fit();
  });
  dialog.addEventListener('close', () => dialog.remove());

  document.body.append(dialog);
  dialog.showModal();
  fit();
  stage.focus();
}
