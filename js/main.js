// Encyclopedia Redesign: progressive enhancements. The page is fully usable without JavaScript.

(function () {
  'use strict';

  const root = document.documentElement;

  /* ---------- Reading settings (text size + theme) ---------- */
  function loadSettings() {
    try { return JSON.parse(localStorage.getItem('appearance') || '{}'); } catch (e) { return {}; }
  }
  function saveSettings(settings) {
    try { localStorage.setItem('appearance', JSON.stringify(settings)); } catch (e) { /* storage unavailable */ }
  }

  const settings = loadSettings();
  document.querySelectorAll('.appearance input[type="radio"]').forEach((input) => {
    const saved = settings[input.name];
    if (saved) input.checked = input.value === saved;

    input.addEventListener('change', () => {
      if (!input.checked) return;
      settings[input.name] = input.value;
      const isDefault = (input.name === 'theme' && input.value === 'auto') ||
                        (input.name === 'size' && input.value === 'standard');
      if (isDefault) delete root.dataset[input.name];
      else root.dataset[input.name] = input.value;
      saveSettings(settings);
    });
  });

  /* ---------- Table of contents: highlight the section being read ---------- */
  const tocLinks = Array.from(document.querySelectorAll('.toc__list a'));
  const sections = tocLinks
    .map((link) => document.querySelector(link.getAttribute('href')))
    .filter(Boolean);

  function setCurrent(id) {
    tocLinks.forEach((link) => {
      if (link.getAttribute('href') === '#' + id) link.setAttribute('aria-current', 'true');
      else link.removeAttribute('aria-current');
    });
  }

  // The section being read is the last one whose top has passed 30% of the viewport height.
  function updateCurrent() {
    const line = window.innerHeight * 0.3;
    let current = sections[0];
    sections.forEach((s) => { if (s.getBoundingClientRect().top <= line) current = s; });
    // At the very bottom of the page, the last section is the one being read.
    if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) {
      current = sections[sections.length - 1];
    }
    if (current) setCurrent(current.id);
  }

  if (sections.length) {
    let ticking = false;
    window.addEventListener('scroll', () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => { updateCurrent(); ticking = false; });
    }, { passive: true });
    window.addEventListener('resize', updateCurrent);
    updateCurrent();
  }

  // On narrow screens, start with the contents and settings collapsed so the article comes first.
  if (window.matchMedia('(max-width: 959px)').matches) {
    document.querySelectorAll('.toc__details, .appearance').forEach((d) => { d.open = false; });
  }

  /* ---------- History: expand / collapse all eras ---------- */
  const toggleAll = document.querySelector('[data-toggle-all]');
  if (toggleAll) {
    const eras = Array.from(document.querySelectorAll('.era__more'));
    const sync = () => {
      const allOpen = eras.every((d) => d.open);
      toggleAll.textContent = allOpen ? 'Collapse all eras' : 'Expand all eras';
      toggleAll.setAttribute('aria-expanded', String(allOpen));
    };
    toggleAll.addEventListener('click', () => {
      const open = !eras.every((d) => d.open);
      eras.forEach((d) => { d.open = open; });
      sync();
    });
    eras.forEach((d) => d.addEventListener('toggle', sync));
    sync();
  }

  /* ---------- Roster: sortable columns ---------- */
  const table = document.getElementById('roster-table');
  if (table) {
    const tbody = table.tBodies[0];
    const status = document.getElementById('sort-status');
    const headers = Array.from(table.tHead.rows[0].cells);

    const cellValue = (row, col, type) => {
      const cell = row.cells[col];
      const raw = cell.dataset.value || cell.textContent.trim();
      return type === 'number' ? parseFloat(raw) : raw.toLowerCase();
    };

    headers.forEach((th) => {
      const button = th.querySelector('button');
      if (!button) return;
      button.addEventListener('click', () => {
        const col = Number(button.dataset.col);
        const type = button.dataset.sort;
        const direction = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';

        const rows = Array.from(tbody.rows);
        rows.sort((a, b) => {
          const x = cellValue(a, col, type);
          const y = cellValue(b, col, type);
          const cmp = type === 'number' ? x - y : x.localeCompare(y);
          return direction === 'ascending' ? cmp : -cmp;
        });
        rows.forEach((r) => tbody.appendChild(r));

        headers.forEach((h) => h.removeAttribute('aria-sort'));
        th.setAttribute('aria-sort', direction);
        if (status) status.textContent = `Roster sorted by ${button.textContent}, ${direction}.`;
      });
    });
  }
})();
