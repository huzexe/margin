// Callout block: Definition, Example, Key takeaways, Please verify.

import { isBlank, sanitize } from './sanitize.js';

const KINDS = {
  definition: 'Definition',
  example: 'Example',
  takeaway: 'Key takeaways',
  verify: 'Please verify',
};

const ICON = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round"><path d="M5 4v16"/><path d="M9 7h10M9 12h10M9 17h6"/></svg>';

export class Callout {
  static get toolbox() { return { title: 'Callout', icon: ICON }; }
  static get enableLineBreaks() { return true; }
  // Tags Editor.js keeps when it cleans the saved text (without this it strips lists)
  static get sanitize() {
    const keep = { b: true, strong: true, i: true, em: true, u: true, mark: true, sub: true, sup: true,
      br: true, ul: true, ol: true, li: true, code: { class: 'inline-code' } };
    return { text: keep, kind: false };
  }
  static get isReadOnlySupported() { return true; }

  constructor({ data, readOnly }) {
    this.kind = KINDS[data?.kind] ? data.kind : 'definition';
    this.text = sanitize(data?.text || '');
    this.readOnly = readOnly;
  }

  render() {
    this.wrapper = document.createElement('div');
    this.label = document.createElement('span');
    this.label.className = 'callout-label';
    this.label.contentEditable = 'false';
    this.body = document.createElement('div');
    this.body.className = 'callout-body';
    this.body.contentEditable = String(!this.readOnly);
    this.body.dataset.placeholder = 'Write here…';
    this.body.innerHTML = this.text;
    this.wrapper.append(this.label, this.body);
    this.paint();
    return this.wrapper;
  }

  paint() {
    this.wrapper.className = `callout callout-${this.kind}`;
    this.label.textContent = KINDS[this.kind];
  }

  // Block menu (⋮⋮ button): change the box type
  renderSettings() {
    return Object.entries(KINDS).map(([kind, label]) => ({
      icon: ICON,
      label,
      isActive: kind === this.kind,
      closeOnActivate: true,
      onActivate: () => { this.kind = kind; this.paint(); },
    }));
  }

  save() {
    return { kind: this.kind, text: sanitize(this.body.innerHTML) };
  }

  validate(data) {
    return !isBlank(data.text);
  }
}
