// Flashcards block: edit question/answer pairs, or switch to Practice to reveal answers one by one.

import { isBlank, sanitize } from './sanitize.js';

const ICON = '<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round"><rect x="3" y="6" width="14" height="12" rx="2"/><path d="M7 3h12a2 2 0 0 1 2 2v10"/></svg>';

export class Flashcards {
  static get toolbox() { return { title: 'Flashcards', icon: ICON }; }
  static get enableLineBreaks() { return true; }
  static get isReadOnlySupported() { return true; }

  constructor({ data, readOnly }) {
    this.cards = (data?.cards || []).map(c => ({ question: sanitize(c.question), answer: sanitize(c.answer) }));
    if (!this.cards.length) this.cards.push({ question: '', answer: '' });
    this.readOnly = readOnly;
    this.practice = false;
  }

  render() {
    this.wrapper = document.createElement('div');
    this.wrapper.className = 'flashcards-block';

    const bar = document.createElement('div');
    bar.className = 'flashcards-bar';
    bar.contentEditable = 'false';
    this.count = document.createElement('span');
    this.count.className = 'flashcards-count';
    this.toggle = document.createElement('button');
    this.toggle.type = 'button';
    this.toggle.className = 'btn btn-sm';
    this.toggle.addEventListener('click', () => {
      this.collect();
      this.practice = !this.practice;
      this.draw();
    });
    bar.append(this.count, this.toggle);

    this.list = document.createElement('div');
    this.list.className = 'flashcards';
    this.wrapper.append(bar, this.list);
    this.draw();
    return this.wrapper;
  }

  // Read the current text from the editable cards into this.cards
  collect() {
    if (this.practice) return;
    this.cards = [...this.list.querySelectorAll('.flashcard-edit')].map(card => ({
      question: sanitize(card.querySelector('.flashcard-q').innerHTML),
      answer: sanitize(card.querySelector('.flashcard-a').innerHTML),
    }));
  }

  field(cls, html, placeholder) {
    const div = document.createElement('div');
    div.className = cls;
    div.contentEditable = String(!this.readOnly);
    div.dataset.placeholder = placeholder;
    div.innerHTML = html;
    return div;
  }

  draw() {
    const n = this.cards.filter(c => !isBlank(c.question)).length;
    this.count.textContent = `${n} ${n === 1 ? 'card' : 'cards'}`;
    this.toggle.textContent = this.practice ? 'Done' : 'Practice';
    this.toggle.hidden = n === 0;
    this.list.replaceChildren();

    if (this.practice || this.readOnly) {
      for (const card of this.cards.filter(c => !isBlank(c.question))) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'flashcard';
        button.setAttribute('aria-expanded', 'false');
        button.innerHTML = `<span class="flashcard-q">${card.question}</span><span class="flashcard-a">${card.answer}</span><span class="flashcard-hint">Click to show answer</span>`;
        button.addEventListener('click', () => {
          button.setAttribute('aria-expanded', String(button.getAttribute('aria-expanded') !== 'true'));
        });
        this.list.append(button);
      }
      return;
    }

    this.cards.forEach((card, index) => {
      const item = document.createElement('div');
      item.className = 'flashcard-edit';
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'btn btn-ghost btn-sm flashcard-remove';
      remove.textContent = 'Remove';
      remove.contentEditable = 'false';
      remove.addEventListener('click', () => {
        this.collect();
        this.cards.splice(index, 1);
        if (!this.cards.length) this.cards.push({ question: '', answer: '' });
        this.draw();
      });
      item.append(
        this.field('flashcard-q', card.question, 'Question'),
        this.field('flashcard-a', card.answer, 'Answer'),
        remove,
      );
      this.list.append(item);
    });

    const add = document.createElement('button');
    add.type = 'button';
    add.className = 'btn btn-ghost btn-sm flashcard-add';
    add.textContent = '+ Add card';
    add.addEventListener('click', () => {
      this.collect();
      this.cards.push({ question: '', answer: '' });
      this.draw();
      this.list.querySelectorAll('.flashcard-q')[this.cards.length - 1]?.focus();
    });
    this.list.append(add);
  }

  save() {
    this.collect();
    return { cards: this.cards.filter(c => !isBlank(c.question) && !isBlank(c.answer)) };
  }

  validate(data) {
    return data.cards.length > 0;
  }
}
