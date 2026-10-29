// Diagram block: Mermaid code drawn as a diagram, with a caption and an "Edit diagram" panel.
// If the code can't be drawn, it shows a text outline with Try again / Edit instead of a broken picture.

import { diagramOutline, onThemeChange, renderDiagram, requestFix } from '../diagrams.js';
import { debounce } from '../ui.js';
import { openZoom } from '../zoom.js';

const ICON = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round"><rect x="3" y="3" width="7" height="6" rx="1"/><rect x="14" y="15" width="7" height="6" rx="1"/><path d="M6.5 9v4.5a1.5 1.5 0 0 0 1.5 1.5h6"/></svg>';
const STARTER = 'flowchart TD\n  A["Start"] --> B["Next step"]';

export class Diagram {
  static get toolbox() { return { title: 'Diagram', icon: ICON }; }
  static get enableLineBreaks() { return true; }
  static get isReadOnlySupported() { return true; }

  constructor({ data, readOnly, block }) {
    this.code = data?.code || STARTER;
    this.caption = data?.caption || '';
    this.readOnly = readOnly;
    this.block = block;
    this.isNew = !data?.code;
  }

  render() {
    const figure = document.createElement('figure');
    figure.className = 'diagram diagram-block';

    this.canvas = document.createElement('div');
    this.canvas.className = 'diagram-canvas';
    this.canvas.contentEditable = 'false';

    this.captionEl = document.createElement('figcaption');
    this.captionEl.contentEditable = String(!this.readOnly);
    this.captionEl.dataset.placeholder = 'Caption';
    this.captionEl.textContent = this.caption;
    this.captionEl.addEventListener('keydown', e => { if (e.key === 'Enter') e.preventDefault(); });

    figure.append(this.canvas, this.captionEl);

    const tools = document.createElement('div');
    tools.className = 'diagram-tools';
    tools.contentEditable = 'false';
    tools.append(this.zoomButton());
    figure.append(tools);
    if (!this.readOnly) {
      this.editButton = this.button('Edit diagram', () => this.toggleEditor());
      tools.append(this.editButton);
      figure.append(this.buildEditor());
    }

    this.draw();
    onThemeChange(() => { if (this.canvas.isConnected) this.draw(); });
    if (this.isNew && !this.readOnly) queueMicrotask(() => this.toggleEditor(true));
    return figure;
  }

  zoomButton() {
    const b = this.button('Enlarge', () => {
      const svg = this.canvas.querySelector('svg');
      if (svg) openZoom(svg.outerHTML, this.captionEl.textContent.trim());
    });
    b.title = 'Open full screen to zoom';
    return b;
  }

  button(label, onClick, cls = 'btn btn-ghost btn-sm') {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = cls;
    b.textContent = label;
    b.addEventListener('click', onClick);
    return b;
  }

  buildEditor() {
    this.panel = document.createElement('div');
    this.panel.className = 'diagram-editor';
    this.panel.contentEditable = 'false';
    this.panel.hidden = true;

    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = 'Diagram code (Mermaid)';
    this.textarea = document.createElement('textarea');
    this.textarea.className = 'diagram-code';
    this.textarea.spellcheck = false;
    this.textarea.rows = 8;
    this.textarea.value = this.code;
    label.append(this.textarea);

    this.codeError = document.createElement('p');
    this.codeError.className = 'field-error';
    this.codeError.hidden = true;

    const hint = document.createElement('p');
    hint.className = 'field-hint';
    hint.textContent = 'Changes show above as you type. Put labels in double quotes, e.g. A["Step one"] --> B["Step two"].';

    const actions = document.createElement('div');
    actions.className = 'diagram-editor-actions';
    actions.append(this.button('Done', () => this.toggleEditor(false), 'btn btn-sm'));

    const preview = debounce(() => {
      this.code = this.textarea.value;
      this.draw();
      this.block?.dispatchChange?.();
    }, 400);
    this.textarea.addEventListener('input', preview);
    this.textarea.addEventListener('keydown', e => {
      e.stopPropagation(); // keep Enter, Tab and Backspace inside the code box
      if (e.key === 'Escape') this.toggleEditor(false);
      if (e.key === 'Tab') {
        e.preventDefault();
        this.textarea.setRangeText('  ', this.textarea.selectionStart, this.textarea.selectionEnd, 'end');
        preview();
      }
    });

    this.panel.append(label, this.codeError, hint, actions);
    return this.panel;
  }

  toggleEditor(open = this.panel.hidden) {
    this.panel.hidden = !open;
    this.editButton.textContent = open ? 'Close editor' : 'Edit diagram';
    if (open) { this.textarea.value = this.code; this.textarea.focus(); }
  }

  async draw() {
    const code = this.code.trim();
    const drawId = (this.drawId = (this.drawId || 0) + 1);
    try {
      const svg = await renderDiagram(code);
      if (drawId !== this.drawId) return; // a newer draw started meanwhile
      this.canvas.innerHTML = svg;
      this.canvas.classList.remove('is-broken');
      if (this.codeError) this.codeError.hidden = true;
    } catch (err) {
      if (drawId !== this.drawId) return;
      this.showFallback(String(err?.message || err));
    }
  }

  showFallback(message) {
    this.canvas.classList.add('is-broken');
    if (this.codeError) {
      this.codeError.textContent = message.split('\n')[0].slice(0, 200);
      this.codeError.hidden = false;
    }
    // While editing, keep it calm: the error shows under the code box
    if (this.panel && !this.panel.hidden) {
      this.canvas.replaceChildren(Object.assign(document.createElement('p'), {
        className: 'diagram-note', textContent: 'The diagram will appear here once the code is valid.',
      }));
      return;
    }
    const box = document.createElement('div');
    box.className = 'diagram-fallback';
    const title = document.createElement('p');
    title.className = 'diagram-note';
    title.textContent = "This diagram couldn't be drawn. Its main points:";
    const list = document.createElement('ul');
    for (const label of diagramOutline(this.code).slice(0, 15)) {
      const li = document.createElement('li');
      li.textContent = label;
      list.append(li);
    }
    box.append(title);
    if (list.children.length) box.append(list);
    if (!this.readOnly) {
      const actions = document.createElement('div');
      actions.className = 'diagram-editor-actions';
      const retry = this.button('Try again', async () => {
        retry.disabled = true;
        retry.textContent = 'Fixing…';
        try {
          this.code = await requestFix(this.code, message);
          if (this.textarea) this.textarea.value = this.code;
          await this.draw();
          this.block?.dispatchChange?.();
        } catch (err) {
          retry.disabled = false;
          retry.textContent = 'Try again';
          title.textContent = `Couldn't fix it: ${err.message}`;
        }
      }, 'btn btn-sm');
      actions.append(retry, this.button('Edit diagram', () => this.toggleEditor(true)));
      box.append(actions);
    }
    this.canvas.replaceChildren(box);
  }

  save() {
    return { code: this.code.trim(), caption: this.captionEl.textContent.trim() };
  }

  validate(data) {
    return Boolean(data.code);
  }
}
