// Formula block: LaTeX shown with KaTeX, plus a one-line explanation. Click the formula to edit it.

import { sanitize } from './sanitize.js';

const ICON = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M18 5H7l6 7-6 7h11"/></svg>';

export class Formula {
  static get toolbox() { return { title: 'Formula', icon: ICON }; }
  static get enableLineBreaks() { return true; }
  static get isReadOnlySupported() { return true; }

  constructor({ data, readOnly }) {
    this.latex = data?.latex || '';
    this.text = sanitize(data?.text || '');
    this.readOnly = readOnly;
  }

  render() {
    const wrapper = document.createElement('div');
    wrapper.className = 'callout callout-formula formula-block';

    const label = document.createElement('span');
    label.className = 'callout-label';
    label.textContent = 'Formula';

    this.display = document.createElement('div');
    this.display.className = 'formula-display';
    this.display.tabIndex = this.readOnly ? -1 : 0;
    this.display.title = this.readOnly ? '' : 'Click to edit the formula';

    this.input = document.createElement('textarea');
    this.input.className = 'formula-input';
    this.input.rows = 2;
    this.input.spellcheck = false;
    this.input.placeholder = 'LaTeX, e.g. E = mc^2';
    this.input.setAttribute('aria-label', 'Formula (LaTeX)');
    this.input.value = this.latex;
    this.input.hidden = true;

    this.explain = document.createElement('div');
    this.explain.className = 'formula-text';
    this.explain.contentEditable = String(!this.readOnly);
    this.explain.dataset.placeholder = 'What the symbols mean…';
    this.explain.innerHTML = this.text;

    wrapper.append(label, this.display, this.input, this.explain);
    this.draw();

    if (!this.readOnly) {
      const open = () => { this.input.hidden = false; this.input.focus(); };
      this.display.addEventListener('click', open);
      this.display.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); open(); } });
      this.input.addEventListener('input', () => { this.latex = this.input.value; this.draw(); });
      this.input.addEventListener('blur', () => { if (this.latex.trim()) this.input.hidden = true; });
      this.input.addEventListener('keydown', e => {
        if (e.key === 'Escape') { e.stopPropagation(); this.input.blur(); }
      });
      if (!this.latex.trim()) this.input.hidden = false; // new, empty formula: start editing
    }
    return wrapper;
  }

  draw() {
    const latex = this.latex.trim();
    this.display.classList.toggle('is-empty', !latex);
    if (!latex) {
      this.display.textContent = this.readOnly ? '' : 'Click to add a formula';
      return;
    }
    if (!window.katex) {
      this.display.textContent = latex;
      return;
    }
    // trust:false (the default) blocks links and HTML commands inside formulas
    window.katex.render(latex, this.display, { displayMode: true, throwOnError: false, strict: false });
  }

  save() {
    return { latex: this.input.value.trim(), text: sanitize(this.explain.innerHTML) };
  }

  validate(data) {
    return Boolean(data.latex);
  }
}
