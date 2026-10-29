// Keeps only simple formatting tags in editable text (callouts, formulas, flashcards).
// Uses a <template>, whose content is inert: nothing in it runs or loads while it is cleaned.

const ALLOWED = new Set(['B', 'STRONG', 'I', 'EM', 'U', 'CODE', 'BR', 'UL', 'OL', 'LI', 'MARK', 'SUB', 'SUP']);
const DROP = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'TEMPLATE', 'SVG', 'MATH', 'IMG', 'VIDEO', 'AUDIO']);

function clean(node) {
  for (const child of [...node.childNodes]) {
    if (child.nodeType === Node.TEXT_NODE) continue;
    if (child.nodeType !== Node.ELEMENT_NODE || DROP.has(child.tagName)) {
      child.remove();
      continue;
    }
    clean(child);
    if (!ALLOWED.has(child.tagName)) {
      child.replaceWith(...child.childNodes); // keep the text, lose the tag
      continue;
    }
    const keepClass = child.tagName === 'CODE' && child.classList.contains('inline-code');
    for (const attr of [...child.attributes]) child.removeAttribute(attr.name);
    if (keepClass) child.className = 'inline-code';
  }
}

export function sanitize(html) {
  const template = document.createElement('template');
  template.innerHTML = html || '';
  clean(template.content);
  return template.innerHTML.trim();
}

export function isBlank(html) {
  const template = document.createElement('template');
  template.innerHTML = html || '';
  return !template.content.textContent.trim();
}
