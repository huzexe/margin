// Mermaid helpers: theme-aware rendering, validation, and the automatic "fix once" step.

import { api } from './api.js';

let configuredFor = null; // theme the current Mermaid config was built for
let queue = Promise.resolve(); // Mermaid renders one diagram at a time
let counter = 0;

function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function currentTheme() {
  const t = document.documentElement.dataset.theme;
  if (t) return t;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function configure() {
  const theme = currentTheme();
  if (configuredFor === theme) return;
  window.mermaid.initialize({
    startOnLoad: false,
    securityLevel: 'strict', // labels are sanitized; no clicks or scripts in diagrams
    theme: 'base',
    fontFamily: token('--font-ui'),
    flowchart: { htmlLabels: true, useMaxWidth: true },
    themeVariables: {
      fontFamily: token('--font-ui'),
      fontSize: '14px',
      background: token('--surface'),
      primaryColor: token('--surface-2'),
      primaryBorderColor: token('--rule-strong'),
      primaryTextColor: token('--ink'),
      secondaryColor: token('--accent-soft'),
      tertiaryColor: token('--surface'),
      lineColor: token('--muted'),
      textColor: token('--ink'),
      edgeLabelBackground: token('--surface'),
      noteBkgColor: token('--example-bg'),
      noteTextColor: token('--ink'),
      actorBkg: token('--surface-2'),
      actorBorder: token('--rule-strong'),
      actorTextColor: token('--ink'),
      signalColor: token('--muted'),
      signalTextColor: token('--ink'),
    },
  });
  configuredFor = theme;
}

/** Returns the SVG markup for `code`, or throws an Error with Mermaid's message. */
export function renderDiagram(code) {
  const job = queue.then(async () => {
    configure();
    const id = `mmd-${Date.now().toString(36)}-${counter++}`;
    try {
      const { svg } = await window.mermaid.render(id, code);
      return svg;
    } finally {
      document.getElementById(id)?.remove();
      document.getElementById(`d${id}`)?.remove(); // temporary container Mermaid leaves on errors
    }
  });
  queue = job.catch(() => {});
  return job;
}

/** True if Mermaid can parse the code; otherwise the error message. */
export async function checkDiagram(code) {
  try {
    configure();
    await window.mermaid.parse(code);
    return true;
  } catch (err) {
    return String(err?.message || err).slice(0, 800);
  }
}

/** Ask the server for a corrected version. Returns the new code (not checked yet). */
export async function requestFix(code, error) {
  const result = await api('/api/notes/diagrams/fix', { method: 'POST', body: { code, error } });
  return result.code;
}

/**
 * For freshly generated blocks: each diagram that doesn't parse gets one automatic fix.
 * If the fix also fails, the original stays and the block shows its fallback.
 */
export async function repairDiagrams(blocks, onProgress) {
  for (const block of blocks) {
    if (block.type !== 'diagram') continue;
    const ok = await checkDiagram(block.data.code);
    if (ok === true) continue;
    onProgress?.('Checking diagrams…');
    try {
      const fixed = await requestFix(block.data.code, ok);
      if ((await checkDiagram(fixed)) === true) block.data.code = fixed;
    } catch { /* keep the original; the block offers Try again */ }
  }
  return blocks;
}

/** Node labels from Mermaid code, used for the text outline when a diagram can't be drawn. */
export function diagramOutline(code) {
  const labels = [];
  const re = /"([^"\n]{1,120})"|\[([^[\]"\n]{1,120})\]|\(\(?([^()"\n]{1,120})\)?\)|\{([^{}"\n]{1,120})\}/g;
  for (const m of code.matchAll(re)) {
    const label = (m[1] || m[2] || m[3] || m[4] || '').trim();
    if (label && !labels.includes(label)) labels.push(label);
  }
  return labels;
}

// Re-render diagrams when the theme changes
export function onThemeChange(fn) {
  new MutationObserver(fn).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', fn);
}
