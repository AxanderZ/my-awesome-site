// Encyclopedia Redesign — progressive enhancement for every page.
// Pages are fully readable without JavaScript; these scripts add suggestions,
// reading aids, and the live search results page.
(function () {
  'use strict';

  const root = document.documentElement;
  const API = 'https://en.wikipedia.org/w/api.php';
  const REST = 'https://en.wikipedia.org/w/rest.php/v1';
  const WIKI = 'https://en.wikipedia.org/wiki/';
  // Articles rebuilt in this site (links to them stay local).
  const LOCAL = {
    'Golden State Warriors': 'wiki/Golden_State_Warriors.html',
    'Stephen Curry': 'wiki/Stephen_Curry.html',
  };

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function articleUrl(title, prefix) {
    if (LOCAL[title]) return (prefix || '') + LOCAL[title];
    return WIKI + encodeURIComponent(title.replace(/ /g, '_'));
  }

  /* ------------------------------------------------------------------ */
  /* Display settings (text size, width, theme)                          */
  /* ------------------------------------------------------------------ */
  (function display() {
    const toggle = $('.display__toggle');
    const panel = $('#display-panel');
    if (!toggle || !panel) return;
    let settings = {};
    try { settings = JSON.parse(localStorage.getItem('display') || '{}'); } catch (e) { /* storage blocked */ }

    $$('input[type="radio"]', panel).forEach((input) => {
      if (settings[input.name]) input.checked = input.value === settings[input.name];
      input.addEventListener('change', () => {
        settings[input.name] = input.value;
        const defaults = { theme: 'auto', size: 'standard', width: 'standard' };
        if (input.value === defaults[input.name]) delete root.dataset[input.name];
        else root.dataset[input.name] = input.value;
        try { localStorage.setItem('display', JSON.stringify(settings)); } catch (e) { /* ignore */ }
      });
    });

    const setOpen = (open) => {
      panel.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
    };
    toggle.addEventListener('click', () => setOpen(panel.hidden));
    document.addEventListener('click', (e) => {
      if (!panel.hidden && !panel.contains(e.target) && !toggle.contains(e.target)) setOpen(false);
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !panel.hidden) { setOpen(false); toggle.focus(); }
    });
  })();

  /* ------------------------------------------------------------------ */
  /* Search suggestions (ARIA 1.2 combobox with listbox popup)           */
  /* ------------------------------------------------------------------ */
  $$('form.search').forEach((form) => {
    const input = $('input[role="combobox"]', form);
    const list = $('[role="listbox"]', form);
    const status = $('[role="status"]', form);
    const prefix = form.dataset.prefix || '';
    if (!input || !list) return;
    let items = [];
    let active = -1;
    let timer = 0;
    let controller = null;

    const close = () => {
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      active = -1;
    };
    const highlight = (i) => {
      const opts = $$('[role="option"]', list);
      opts.forEach((o, j) => o.setAttribute('aria-selected', String(j === i)));
      active = i;
      if (i >= 0 && opts[i]) {
        input.setAttribute('aria-activedescendant', opts[i].id);
        opts[i].scrollIntoView({ block: 'nearest' });
      } else {
        input.removeAttribute('aria-activedescendant');
      }
    };
    const go = (i) => { if (items[i]) window.location.href = items[i].href; };

    const render = (q, pages) => {
      items = pages.map((p) => ({
        title: p.title,
        desc: p.description || '',
        thumb: p.thumbnail && p.thumbnail.url ? (p.thumbnail.url.startsWith('//') ? 'https:' + p.thumbnail.url : p.thumbnail.url) : '',
        href: articleUrl(p.title, prefix),
        local: Boolean(LOCAL[p.title]),
      }));
      items.push({ all: true, title: q, href: prefix + 'search.html?q=' + encodeURIComponent(q) });
      list.innerHTML = items.map((it, i) => it.all
        ? `<li role="option" id="${input.id}-opt-${i}" aria-selected="false" class="opt__all">Search all articles for “${esc(it.title)}”</li>`
        : `<li role="option" id="${input.id}-opt-${i}" aria-selected="false">` +
          (it.thumb ? `<img class="opt__thumb" src="${esc(it.thumb)}" alt="">` : '<span class="opt__thumb" aria-hidden="true"></span>') +
          `<span class="opt__text"><span class="opt__title">${esc(it.title)}${it.local ? ' <span class="badge badge--local">Redesigned</span>' : ''}</span>` +
          (it.desc ? `<span class="opt__desc">${esc(it.desc)}</span>` : '') + '</span></li>').join('');
      list.hidden = false;
      input.setAttribute('aria-expanded', 'true');
      active = -1;
      if (status) status.textContent = `${pages.length} suggestion${pages.length === 1 ? '' : 's'} available. Use the up and down arrow keys to review them.`;
    };

    input.addEventListener('input', () => {
      clearTimeout(timer);
      const q = input.value.trim();
      if (!q) { close(); return; }
      timer = setTimeout(async () => {
        if (controller) controller.abort();
        controller = new AbortController();
        try {
          const r = await fetch(`${REST}/search/title?q=${encodeURIComponent(q)}&limit=6`, { signal: controller.signal });
          if (!r.ok) throw new Error(r.status);
          const data = await r.json();
          if (input.value.trim() === q) render(q, data.pages || []);
        } catch (e) {
          if (e.name !== 'AbortError') close();
        }
      }, 160);
    });

    input.addEventListener('keydown', (e) => {
      const open = !list.hidden;
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (!open && items.length) { list.hidden = false; input.setAttribute('aria-expanded', 'true'); }
        highlight(Math.min(active + 1, items.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        highlight(Math.max(active - 1, -1));
      } else if (e.key === 'Enter' && open && active >= 0) {
        e.preventDefault();
        go(active);
      } else if (e.key === 'Escape') {
        if (open) { e.preventDefault(); close(); }
      }
    });
    list.addEventListener('mousedown', (e) => {
      const li = e.target.closest('[role="option"]');
      if (!li) return;
      e.preventDefault();
      go($$('[role="option"]', list).indexOf(li));
    });
    input.addEventListener('blur', () => setTimeout(close, 120));
  });

  /* ------------------------------------------------------------------ */
  /* Article reading aids                                                 */
  /* ------------------------------------------------------------------ */
  const article = $('.article');
  if (article) {
    // Open any collapsed <details> that contains the target, so links always land somewhere visible.
    const reveal = (id, openOwn) => {
      const el = id && document.getElementById(decodeURIComponent(id));
      if (!el) return null;
      let d = el.closest('details');
      while (d) { d.open = true; d = d.parentElement && d.parentElement.closest('details'); }
      if (openOwn) {
        const owner = el.closest('summary') && el.closest('summary').parentElement;
        if (owner && owner.tagName === 'DETAILS') owner.open = true;
      }
      return el;
    };
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[href^="#"]');
      if (!a || a.getAttribute('href').length < 2) return;
      reveal(a.getAttribute('href').slice(1), true);
    });
    const fromHash = () => {
      const el = reveal(location.hash.slice(1), true);
      if (el) requestAnimationFrame(() => el.scrollIntoView());
    };
    window.addEventListener('hashchange', fromHash);
    if (location.hash) fromHash();

    // Expand / collapse every subsection in a section.
    $$('[data-expand]').forEach((btn) => {
      const section = btn.closest('.section');
      const all = $$('details.sub', section);
      const label = btn.textContent;
      const sync = () => {
        const open = all.every((d) => d.open);
        btn.textContent = open ? 'Collapse all' : label;
        btn.setAttribute('aria-expanded', String(open));
      };
      btn.addEventListener('click', () => {
        const open = !all.every((d) => d.open);
        all.forEach((d) => { d.open = open; });
        sync();
      });
      all.forEach((d) => d.addEventListener('toggle', sync));
      sync();
    });

    // Table of contents: subsection toggles, current-section highlight, reading progress.
    const toc = $('.toc');
    const tocBox = $('.toc__box');
    if (tocBox && window.matchMedia('(max-width: 1039px)').matches) tocBox.open = false;
    $$('.toc__toggle').forEach((btn) => {
      btn.addEventListener('click', () => {
        const li = btn.closest('.has-subs');
        const open = !li.classList.contains('is-open');
        li.classList.toggle('is-open', open);
        li.dataset.user = open ? 'open' : 'closed';
        btn.setAttribute('aria-expanded', String(open));
      });
    });
    const links = toc ? $$('a[href^="#"]', toc) : [];
    const targets = links.map((a) => document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)))).filter(Boolean);
    const bar = $('.progress__bar');
    let ticking = false;
    const update = () => {
      ticking = false;
      const line = window.innerHeight * 0.25;
      let current = null;
      for (const t of targets) {
        if (t.getBoundingClientRect().top <= line) current = t; else break;
      }
      links.forEach((a) => {
        const on = current && a.getAttribute('href') === '#' + current.id;
        if (on) a.setAttribute('aria-current', 'true'); else a.removeAttribute('aria-current');
      });
      // Keep the active group's subsections visible in the contents list.
      const activeLink = links.find((a) => a.hasAttribute('aria-current'));
      $$('.has-subs', toc || document).forEach((li) => {
        const contains = activeLink && li.contains(activeLink);
        if (li.dataset.user) return;
        li.classList.toggle('is-open', Boolean(contains));
        const b = $('.toc__toggle', li);
        if (b) b.setAttribute('aria-expanded', String(Boolean(contains)));
      });
      if (bar) {
        const max = document.documentElement.scrollHeight - window.innerHeight;
        bar.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`;
      }
    };
    const onScroll = () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } };
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    document.addEventListener('toggle', onScroll, true);
    update();

    // Citation previews: hover or focus a marker to read its source without jumping away.
    const pop = $('#cite-pop');
    let hideTimer = 0;
    let owner = null;
    const hide = () => {
      if (!pop) return;
      pop.hidden = true;
      if (owner) owner.removeAttribute('aria-describedby');
      owner = null;
    };
    const show = (a) => {
      const li = document.getElementById(decodeURIComponent(a.getAttribute('href').slice(1)));
      if (!li || !pop) return;
      clearTimeout(hideTimer);
      const clone = li.cloneNode(true);
      $$('.backrefs', clone).forEach((n) => n.remove());
      $$('[id]', clone).forEach((n) => n.removeAttribute('id'));
      const isNote = a.closest('.cite--note');
      pop.innerHTML = `<span class="cite-pop__label">${isNote ? 'Note' : 'Source'} ${esc(a.textContent)}</span>`;
      const body = document.createElement('p');
      body.innerHTML = clone.innerHTML;
      pop.appendChild(body);
      pop.hidden = false;
      const r = a.getBoundingClientRect();
      const w = pop.offsetWidth;
      let left = window.scrollX + r.left + r.width / 2 - w / 2;
      left = Math.max(window.scrollX + 12, Math.min(left, window.scrollX + document.documentElement.clientWidth - w - 12));
      let top = window.scrollY + r.bottom + 8;
      if (r.bottom + pop.offsetHeight + 16 > window.innerHeight) top = window.scrollY + r.top - pop.offsetHeight - 8;
      pop.style.left = left + 'px';
      pop.style.top = top + 'px';
      if (owner && owner !== a) owner.removeAttribute('aria-describedby');
      owner = a;
      a.setAttribute('aria-describedby', 'cite-pop');
    };
    const later = () => { clearTimeout(hideTimer); hideTimer = setTimeout(hide, 220); };
    article.addEventListener('mouseover', (e) => { const a = e.target.closest('sup.cite a'); if (a) show(a); });
    article.addEventListener('mouseout', (e) => { if (e.target.closest('sup.cite a')) later(); });
    article.addEventListener('focusin', (e) => { const a = e.target.closest('sup.cite a'); if (a) show(a); else if (owner) hide(); });
    article.addEventListener('focusout', (e) => { if (e.target.closest('sup.cite a')) later(); });
    if (pop) {
      pop.addEventListener('mouseover', () => clearTimeout(hideTimer));
      pop.addEventListener('mouseout', later);
    }
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && pop && !pop.hidden) hide(); });
  }

  /* ------------------------------------------------------------------ */
  /* Sortable tables                                                      */
  /* ------------------------------------------------------------------ */
  $$('table[data-sortable]').forEach((table) => {
    const head = table.tHead && table.tHead.rows[0];
    const body = table.tBodies[0];
    if (!head || !body) return;
    const live = document.createElement('p');
    live.className = 'vh';
    live.setAttribute('role', 'status');
    table.parentElement.after(live);
    Array.from(head.cells).forEach((th, col) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'sort-btn';
      while (th.firstChild) btn.appendChild(th.firstChild);
      th.appendChild(btn);
      btn.addEventListener('click', () => {
        const dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
        const val = (row) => {
          const cell = row.cells[col];
          if (!cell) return '';
          return (cell.dataset.value || cell.textContent).trim();
        };
        const rows = Array.from(body.rows);
        const nums = rows.map((r) => parseFloat(val(r).replace(/[,$%]/g, '').replace(/^[–-]$/, '')));
        const numeric = th.dataset.type === 'number' || nums.filter((n) => !isNaN(n)).length >= rows.length * 0.8;
        rows.sort((a, b) => {
          let x = val(a); let y = val(b);
          let c;
          if (numeric) {
            x = parseFloat(x.replace(/[,$%]/g, '')); y = parseFloat(y.replace(/[,$%]/g, ''));
            c = (isNaN(x) ? -Infinity : x) - (isNaN(y) ? -Infinity : y);
          } else {
            c = x.localeCompare(y, undefined, { numeric: true, sensitivity: 'base' });
          }
          return dir === 'ascending' ? c : -c;
        });
        rows.forEach((r) => body.appendChild(r));
        Array.from(head.cells).forEach((c) => c.removeAttribute('aria-sort'));
        th.setAttribute('aria-sort', dir);
        live.textContent = `Sorted by ${btn.textContent.trim()}, ${dir}.`;
      });
    });
  });

  /* ------------------------------------------------------------------ */
  /* Search results page                                                  */
  /* ------------------------------------------------------------------ */
  const results = $('#results');
  if (results) {
    const params = new URLSearchParams(location.search);
    const q = (params.get('q') || '').trim();
    const noRewrite = params.has('norewrite');
    const statusEl = $('#search-status');
    const notice = $('#search-notice');
    const more = $('#more-results');
    let offset = 0;
    let shown = 0;

    const setStatus = (text, busy) => {
      statusEl.textContent = text;
      statusEl.dataset.busy = busy ? 'true' : 'false';
    };
    const fmtDate = (iso) => new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    const snippet = (html) => {
      const tmp = document.createElement('div');
      tmp.innerHTML = html;
      $$('span.searchmatch', tmp).forEach((s) => { const m = document.createElement('mark'); m.textContent = s.textContent; s.replaceWith(m); });
      return Array.from(tmp.childNodes).map((n) => n.nodeName === 'MARK' ? `<mark>${esc(n.textContent)}</mark>` : esc(n.textContent)).join('');
    };
    const resultHtml = (r, top) => {
      const local = Boolean(LOCAL[r.title]);
      return `<li class="result${top ? ' result--top' : ''}">` +
        (top ? '<p class="result__label">Best match</p>' : '') +
        `<h2 class="result__title"><a href="${esc(articleUrl(r.title, ''))}">${esc(r.title)}</a></h2>` +
        `<p class="result__snippet">${snippet(r.snippet || '')}…</p>` +
        `<p class="result__meta">${local ? '<span class="badge badge--local">Redesigned</span>' : '<span class="badge badge--wiki">Opens on Wikipedia</span>'}` +
        `<span>${(r.wordcount || 0).toLocaleString('en-US')} words</span><span>Updated ${fmtDate(r.timestamp)}</span></p></li>`;
    };

    const run = async () => {
      setStatus(offset ? 'Loading more results…' : `Searching for “${q}”…`, true);
      more.hidden = true;
      const url = new URL(API);
      Object.entries({
        action: 'query', list: 'search', srsearch: q, srlimit: '20', sroffset: String(offset),
        srinfo: 'totalhits|suggestion|rewrittenquery', srprop: 'snippet|wordcount|timestamp',
        srenablerewrites: noRewrite ? '0' : '1', format: 'json', formatversion: '2', origin: '*',
      }).forEach(([k, v]) => url.searchParams.set(k, v));
      try {
        const r = await fetch(url);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const data = await r.json();
        const info = (data.query && data.query.searchinfo) || {};
        const list = (data.query && data.query.search) || [];
        if (!offset) {
          notice.innerHTML = '';
          if (info.rewrittenquery) {
            notice.innerHTML = `<p class="search-notice">Showing results for <strong>${esc(info.rewrittenquery)}</strong>. ` +
              `<a href="search.html?q=${encodeURIComponent(q)}&amp;norewrite=1">Search instead for “${esc(q)}”</a>.</p>`;
          } else if (!list.length && info.suggestion) {
            notice.innerHTML = `<p class="search-notice">No results for “${esc(q)}”. Did you mean ` +
              `<a href="search.html?q=${encodeURIComponent(info.suggestion)}">${esc(info.suggestion)}</a>?</p>`;
          }
        }
        if (!list.length && !offset) {
          setStatus(`No articles match “${q}”. Try fewer or different words, or check the spelling.`, false);
          return;
        }
        const effective = (info.rewrittenquery || q).toLowerCase();
        results.insertAdjacentHTML('beforeend', list.map((r, i) =>
          resultHtml(r, !offset && i === 0 && r.title.toLowerCase() === effective)).join(''));
        shown += list.length;
        const total = info.totalhits || shown;
        setStatus(`Showing ${shown.toLocaleString('en-US')} of about ${total.toLocaleString('en-US')} results for “${info.rewrittenquery || q}”.`, false);
        if (data.continue && data.continue.sroffset) {
          offset = data.continue.sroffset;
          more.hidden = false;
        }
      } catch (e) {
        setStatus('Search is unavailable right now.', false);
        notice.innerHTML = `<div class="search-notice search-notice--error"><p>We couldn't reach Wikipedia's search service. Check your connection, then ` +
          `<button type="button" class="btn btn--quiet" id="retry">Try again</button> or ` +
          `<a href="https://en.wikipedia.org/w/index.php?search=${encodeURIComponent(q)}">search on Wikipedia directly</a>.</p></div>`;
        $('#retry').addEventListener('click', () => { notice.innerHTML = ''; run(); });
      }
    };

    if (q) {
      document.title = `“${q}” – Search | Encyclopedia Redesign`;
      $$('form.search input[name="q"]').forEach((i) => { i.value = q; });
      run();
    }
    more.addEventListener('click', run);
  }
})();
