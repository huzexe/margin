// "Regenerate" button on each section of the enhanced notes, with a small request form.

import { el, icon } from './ui.js';

const QUICK = ['Simpler', 'More detail', 'Add an example', 'Shorter'];

/**
 * pane:    the enhanced-notes pane (positioning context)
 * holder:  the editor holder
 * editor:  wrapper from createEditor()
 * onRegenerate({ ids, instruction, signal, setStatus }) does the work and returns when done.
 */
export function setupSectionTools({ pane, holder, editor, isBusy, onRegenerate }) {
  const button = el('button', {
    class: 'btn btn-sm section-regen', type: 'button', hidden: true,
    html: `${icon('refresh')}<span>Regenerate</span>`,
  });
  pane.append(button);
  let current = null; // header element the button belongs to
  let form = null;

  function headerOf(target) {
    const block = target?.closest?.('.ce-block');
    return block && holder.contains(block) && block.querySelector('h2.ce-header') ? block : null;
  }

  function place(block) {
    const paneBox = pane.getBoundingClientRect();
    const box = block.getBoundingClientRect();
    button.style.top = `${box.top - paneBox.top + pane.scrollTop + 2}px`;
    button.style.right = '12px';
  }

  function show(block) {
    if (form || isBusy()) return;
    // Flashcards are not a normal section; they come from the Flashcards option
    const ids = editor.sectionIds(block.dataset.id);
    const hasCards = ids.some(id => holder.querySelector(`.ce-block[data-id="${id}"] .flashcards-block`));
    if (hasCards) { hide(); return; }
    current = block;
    place(block);
    button.hidden = false;
  }

  function hide() {
    if (!form) { button.hidden = true; current = null; }
  }

  holder.addEventListener('mouseover', e => {
    const block = headerOf(e.target);
    if (block) return show(block);
    // Hide once the pointer is clearly away from the heading row
    if (current) {
      const box = current.getBoundingClientRect();
      if (e.clientY > box.bottom + 8 || e.clientY < box.top - 8) hide();
    }
  });
  holder.addEventListener('focusin', e => { const b = headerOf(e.target); if (b) show(b); });
  pane.addEventListener('mouseleave', hide);

  button.addEventListener('click', () => { if (current) openForm(current); });

  function openForm(block) {
    const ids = editor.sectionIds(block.dataset.id);
    const heading = block.textContent.trim();
    const input = el('input', {
      class: 'input', maxlength: 300, autocomplete: 'off',
      placeholder: 'Optional: how should it change?', 'aria-label': 'How should this section change?',
    });
    const status = el('p', { class: 'field-hint', 'aria-live': 'polite' }, `Rewrites “${heading}” only. The rest stays as it is.`);
    const submit = el('button', { class: 'btn btn-primary btn-sm', type: 'submit' }, 'Regenerate');
    const cancel = el('button', { class: 'btn btn-ghost btn-sm', type: 'button' }, 'Cancel');
    const chips = el('div', { class: 'chips' }, ...QUICK.map(q => el('button', {
      class: 'chip', type: 'button', onclick: () => { input.value = q; input.focus(); },
    }, q)));
    form = el('form', { class: 'section-form', role: 'dialog', 'aria-label': `Regenerate section ${heading}` },
      chips, input, status, el('div', { class: 'confirm-actions' }, submit, cancel));
    pane.append(form);
    form.style.top = `${parseFloat(button.style.top) + 36}px`;
    button.hidden = true;
    input.focus();

    let controller = null;
    const close = () => {
      controller?.abort();
      for (const id of ids) holder.querySelector(`.ce-block[data-id="${id}"]`)?.classList.remove('is-regenerating');
      form?.remove();
      form = null;
      current = null;
    };
    cancel.addEventListener('click', close);
    form.addEventListener('keydown', e => { if (e.key === 'Escape') close(); });

    form.addEventListener('submit', async e => {
      e.preventDefault();
      controller = new AbortController();
      submit.disabled = true;
      input.disabled = true;
      chips.hidden = true;
      status.textContent = 'Rewriting this section…';
      for (const id of ids) holder.querySelector(`.ce-block[data-id="${id}"]`)?.classList.add('is-regenerating');
      try {
        await onRegenerate({
          ids, instruction: input.value.trim(), signal: controller.signal,
          setStatus: text => { status.textContent = text; },
        });
        controller = null;
        close();
      } catch (err) {
        if (err.name === 'AbortError') return;
        for (const id of ids) holder.querySelector(`.ce-block[data-id="${id}"]`)?.classList.remove('is-regenerating');
        status.textContent = err.message;
        status.className = 'field-error';
        submit.disabled = false;
        submit.textContent = 'Try again';
        input.disabled = false;
      }
    });
  }
}
