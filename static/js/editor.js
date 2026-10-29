// Rich editor for the enhanced notes (Editor.js, bundled in /static/vendor/editorjs).

import { Callout } from './blocks/callout.js';
import { Diagram } from './blocks/diagram.js';
import { Flashcards } from './blocks/flashcards.js';
import { Formula } from './blocks/formula.js';

const TOOLS = {
  header: { class: window.Header, inlineToolbar: true, config: { levels: [2, 3], defaultLevel: 2, placeholder: 'Heading' } },
  list: { class: window.EditorjsList, inlineToolbar: true, config: { defaultStyle: 'unordered' } },
  callout: { class: Callout, inlineToolbar: true },
  formula: { class: Formula },
  diagram: { class: Diagram },
  table: { class: window.Table, inlineToolbar: true, config: { withHeadings: true } },
  code: { class: window.CodeTool, config: { placeholder: 'Code' } },
  flashcards: { class: Flashcards, inlineToolbar: true },
  inlineCode: { class: window.InlineCode },
};

/** Editor.js tool output differs in key order between runs; compare blocks only. */
export function sameBlocks(a, b) {
  return JSON.stringify(a?.blocks ?? []) === JSON.stringify(b?.blocks ?? []);
}

/**
 * Creates the editor in `holder`. onChange(data) is called (debounced by the caller)
 * whenever the user changes something; it is not called for content set by setData().
 */
export async function createEditor(holder, { data, onChange }) {
  let last = null;    // the editor's own normalized form of the content it was given
  let settled = null; // resolves once loaded content has been rendered and `last` is set

  const editor = new window.EditorJS({
    holder,
    data: data || { blocks: [] },
    tools: TOOLS,
    minHeight: 60,
    placeholder: 'Write here, or use Enhance notes to fill this in.',
    onChange: async () => {
      await settled; // changes caused by loading content are not user edits
      const next = await editor.save();
      if (sameBlocks(next, last)) return;
      last = next;
      onChange(next);
    },
  });
  settled = editor.isReady.then(() => editor.save()).then(d => { last = d; });
  await settled;

  return {
    async setData(next) {
      settled = editor.render(next).then(() => editor.save()).then(d => { last = d; });
      await settled;
    },
    async getData() {
      return editor.save();
    },
    /**
     * Sections start at each level-2 heading. Returns the block ids of the section whose
     * heading has id `headerId` (heading included), in order.
     */
    sectionIds(headerId) {
      const ids = [];
      const els = [...holder.querySelectorAll('.ce-block')];
      const start = els.findIndex(e => e.dataset.id === headerId);
      if (start < 0) return ids;
      for (let i = start; i < els.length; i++) {
        if (i > start && els[i].querySelector('h2.ce-header')) break;
        ids.push(els[i].dataset.id);
      }
      return ids;
    },
    /** Replace the blocks with these ids by `blocks`, keeping their position. */
    async replaceBlocks(ids, blocks) {
      const first = editor.blocks.getBlockIndex(ids[0]);
      for (const id of [...ids].reverse()) {
        const index = editor.blocks.getBlockIndex(id);
        if (index >= 0) editor.blocks.delete(index);
      }
      const at = Math.max(0, first);
      editor.blocks.insertMany(blocks, at);
      const newIds = blocks.map((_, i) => editor.blocks.getBlockByIndex(at + i)?.id).filter(Boolean);
      last = await editor.save();
      return { content: last, ids: newIds };
    },
    focus() {
      editor.focus();
    },
  };
}
