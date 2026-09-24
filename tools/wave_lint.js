// Local approximation of WAVE errors/alerts + axe-core, for iteration before running real WAVE.
window.waveLint = async function () {
  const out = { errors: {}, alerts: {}, contrast: [] };
  const add = (bucket, key, el) => { (out[bucket][key] = out[bucket][key] || []).push(el ? (el.outerHTML || '').slice(0, 140) : ''); };
  const all = [...document.querySelectorAll('body *')];
  // Images
  document.querySelectorAll('figure').forEach((fig) => {
    const cap = fig.querySelector('figcaption'); if (!cap) return;
    fig.querySelectorAll('img').forEach((img) => { const alt = img.alt.trim().toLowerCase().replace(/\.$/, '');
      if (alt && cap.textContent.toLowerCase().includes(alt)) add('alerts', 'redundant alt text', img); });
  });
  document.querySelectorAll('img').forEach((img) => {
    if (!img.hasAttribute('alt')) add('errors', img.closest('a') ? 'linked image missing alt' : 'missing alt', img);
    else if (img.alt.length > 100) add('alerts', 'long alt', img);
    else if (/\.(jpe?g|png|gif|svg)|^(image|photo|picture|graphic|spacer)\b/i.test(img.alt)) add('alerts', 'suspicious alt', img);
    if (img.closest('a') && img.alt === '' && !img.closest('a').textContent.trim()) add('errors', 'linked image empty alt', img);
  });
  // Links / buttons
  const links = [...document.querySelectorAll('a[href]')];
  links.forEach((a, i) => {
    const name = (a.getAttribute('aria-label') || a.textContent || '').trim() || [...a.querySelectorAll('img')].map((x) => x.alt).join('');
    if (!name) add('errors', 'empty link', a);
    if (/\.pdf(\b|$|[?#])/i.test(a.getAttribute('href'))) add('alerts', 'link to PDF', a);
    if (/\.(docx?|xlsx?|pptx?)(\?|$)/i.test(a.getAttribute('href'))) add('alerts', 'link to document', a);
    if (/^(click here|here|more|read more|link)$/i.test(name)) add('alerts', 'suspicious link text', a);
    const next = links[i + 1];
    // WAVE flags consecutive links to the same URL, even with text between them.
    if (next && next.href === a.href && !a.getAttribute('href').startsWith('#') && a.closest('main') && next.closest('main')) add('alerts', 'redundant link', a);
    if (a.hasAttribute('title') && a.title.trim() === a.textContent.trim()) add('alerts', 'redundant title', a);
    if (a.getAttribute('href').startsWith('#') && a.getAttribute('href').length > 1 && !document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)))) add('errors', 'broken same-page link', a);
  });
  document.querySelectorAll('button').forEach((b) => { if (!(b.getAttribute('aria-label') || b.textContent).trim()) add('errors', 'empty button', b); });
  document.querySelectorAll('[title]').forEach((el) => { if (el.tagName !== 'ABBR' && el.tagName !== 'IFRAME') add('alerts', 'title attribute (check redundant)', el); });
  // Forms
  document.querySelectorAll('input:not([type=hidden]), select, textarea').forEach((f) => {
    if (!(f.id && document.querySelector(`label[for="${f.id}"]`)) && !f.closest('label') && !f.getAttribute('aria-label')) add('errors', 'missing form label', f);
  });
  const radiosByName = {};
  document.querySelectorAll('input[type=radio]').forEach((r) => { if (!r.closest('fieldset')) add('alerts', 'missing fieldset', r); });
  // Tables
  document.querySelectorAll('table').forEach((t) => {
    if (!t.querySelector('th')) add('alerts', 'layout table', t);
    t.querySelectorAll('th').forEach((th) => { if (!th.textContent.trim() && !th.querySelector('img[alt]:not([alt=""])')) add('errors', 'empty table header', th); });
    const r1 = t.rows[0];
    if (r1 && r1.cells.length === 1 && r1.cells[0].colSpan > 1 && !t.caption) add('alerts', 'possible table caption', t);
  });
  // Headings
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')];
  if (!document.querySelector('h1')) add('alerts', 'missing h1');
  hs.forEach((h, i) => {
    if (!h.textContent.trim()) add('errors', 'empty heading', h);
    const prev = hs[i - 1];
    if (prev && +h.tagName[1] > +prev.tagName[1] + 1) add('alerts', `skipped heading level (${prev.tagName}→${h.tagName})`, h);
  });
  // Possible headings: short <p> fully bold or large
  document.querySelectorAll('p').forEach((p) => {
    const t = p.textContent.trim();
    if (!t || t.length > 50) return;
    const cs = getComputedStyle(p);
    const kids = [...p.childNodes].filter((n) => !(n.nodeType === 3 && !n.textContent.trim()));
    const styled = (n) => n.nodeType === 1 && (+getComputedStyle(n).fontWeight >= 600 || getComputedStyle(n).fontStyle === 'italic');
    const allStyled = +cs.fontWeight >= 600 || cs.fontStyle === 'italic' || (kids.length && kids.every(styled));
    const fs = parseFloat(cs.fontSize);
    if (fs >= 20 || (fs >= 16 && allStyled)) add('alerts', 'possible heading', p);
  });
  // Misc
  all.forEach((el) => {
    const cs = getComputedStyle(el);
    const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (hasText && parseFloat(cs.fontSize) < 10 && !el.closest('.vh')) add('alerts', 'very small text', el);
    if (hasText && cs.textAlign === 'justify') add('alerts', 'justified text', el);
    if (el.tagName === 'U') add('alerts', 'underlined text', el);
    if (el.hasAttribute('accesskey')) add('alerts', 'accesskey', el);
    if (el.tagName === 'NOSCRIPT') add('alerts', 'noscript', el);
    const ti = el.getAttribute('tabindex'); if (ti && +ti > 0) add('alerts', 'positive tabindex', el);
  });
  // Contrast (text nodes only)
  const lum = (c) => { const m = c.match(/[\d.]+/g).map(Number); const a = m[3] === undefined ? 1 : m[3];
    return [m.slice(0, 3).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }), a]; };
  const L = (rgb) => 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
  const bgOf = (el) => { while (el) { const b = getComputedStyle(el).backgroundColor; if (b && !/rgba\(.*,\s*0\)$/.test(b) && b !== 'transparent') return b; el = el.parentElement; } return 'rgb(255,255,255)'; };
  let min = 99, worst = '';
  all.forEach((el) => {
    if (![...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim())) return;
    if (el.closest('.vh, [hidden], .skip-link')) return;
    const cs = getComputedStyle(el);
    const [fg, fa] = lum(cs.color); const [bg] = lum(bgOf(el));
    const r = (Math.max(L(fg), L(bg)) + 0.05) / (Math.min(L(fg), L(bg)) + 0.05);
    const large = parseFloat(cs.fontSize) >= 24 || (parseFloat(cs.fontSize) >= 18.66 && +cs.fontWeight >= 700);
    if (r < (large ? 3 : 4.5) || fa < 1) out.contrast.push(r.toFixed(2) + ' ' + cs.color + ' on ' + bgOf(el) + ' :: ' + el.tagName + '.' + el.className + ' "' + el.textContent.trim().slice(0, 30) + '"');
    if (r < min) { min = r; worst = r.toFixed(2) + ' ' + el.tagName + '.' + el.className + ' "' + el.textContent.trim().slice(0, 30) + '"'; }
  });
  out.minContrast = worst;
  // axe
  if (!window.axe) await new Promise((res, rej) => { const s = document.createElement('script'); s.src = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js'; s.onload = res; s.onerror = rej; document.head.appendChild(s); });
  const ax = await axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice'] } });
  out.axe = ax.violations.map((v) => `${v.id} (${v.impact}) x${v.nodes.length}: ${v.nodes.slice(0, 2).map((n) => n.target.join(' ')).join(' | ')}`);
  const summarize = (b) => Object.fromEntries(Object.entries(b).map(([k, v]) => [k, `${v.length} e.g. ${v[0] || ''}`]));
  return { errors: summarize(out.errors), alerts: summarize(out.alerts), contrastFails: out.contrast.length, contrastSample: out.contrast.slice(0, 5), minContrast: out.minContrast, axe: out.axe };
};
