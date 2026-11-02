/* Slime Shelf: a scroll-and-read picture book reader. */
(() => {
  'use strict';

  const $ = (sel) => document.querySelector(sel);
  const shelfEl = $('#shelf');
  const mineEl = $('#mine');
  const mineSection = $('#mine-section');
  const pagesEl = $('#pages');
  const readerView = $('#reader-view');
  const shelfView = $('#shelf-view');
  const readerBar = $('#reader-bar');
  const progressFill = $('#progress-fill');
  const pagePill = $('#page-pill');
  const upBtn = $('#up-btn');
  const continueBanner = $('#continue-banner');

  const K_PROG = 'ss.prog.';
  const K_SET = 'ss.settings';

  const settings = Object.assign(
    { size: 1.22, night: false },
    JSON.parse(localStorage.getItem(K_SET) || '{}')
  );

  const state = {
    index: [],
    local: [],
    book: null,
    meta: null,
    total: 0,
    current: 0,
    objectUrls: [],
    restoreTo: 0,
    userScrolled: false,
    filter: 'all',
  };

  /* ---------------- storage ---------------- */

  function saveProgress(id, page, total) {
    try {
      localStorage.setItem(K_PROG + id, JSON.stringify({ page, total, ts: Date.now() }));
    } catch (_) {}
  }

  function getProgress(id) {
    try {
      return JSON.parse(localStorage.getItem(K_PROG + id) || 'null');
    } catch (_) {
      return null;
    }
  }

  function pctOf(meta) {
    const p = getProgress(meta.id);
    if (!p || !p.total) return 0;
    return Math.min(100, Math.round(((p.page + 1) / p.total) * 100));
  }

  /* ---------------- IndexedDB for user books ---------------- */

  let dbPromise = null;
  function db() {
    if (dbPromise) return dbPromise;
    dbPromise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('IndexedDB timeout')), 4000);
      const req = indexedDB.open('slime-shelf', 1);
      req.onupgradeneeded = () => {
        const d = req.result;
        if (!d.objectStoreNames.contains('books')) d.createObjectStore('books', { keyPath: 'id' });
      };
      req.onsuccess = () => { clearTimeout(timer); resolve(req.result); };
      req.onerror = () => { clearTimeout(timer); reject(req.error); };
      req.onblocked = () => { clearTimeout(timer); reject(new Error('IndexedDB blocked')); };
    });
    return dbPromise;
  }

  async function idbAll() {
    const d = await db();
    return new Promise((resolve) => {
      const tx = d.transaction('books', 'readonly').objectStore('books').getAll();
      tx.onsuccess = () => resolve(tx.result || []);
      tx.onerror = () => resolve([]);
    });
  }

  async function idbGet(id) {
    const d = await db();
    return new Promise((resolve) => {
      const tx = d.transaction('books', 'readonly').objectStore('books').get(id);
      tx.onsuccess = () => resolve(tx.result || null);
      tx.onerror = () => resolve(null);
    });
  }

  async function idbPut(obj) {
    const d = await db();
    return new Promise((resolve) => {
      const tx = d.transaction('books', 'readwrite').objectStore('books').put(obj);
      tx.onsuccess = () => resolve(true);
      tx.onerror = () => resolve(false);
    });
  }

  async function idbDel(id) {
    const d = await db();
    return new Promise((resolve) => {
      const tx = d.transaction('books', 'readwrite').objectStore('books').delete(id);
      tx.onsuccess = () => resolve(true);
      tx.onerror = () => resolve(false);
    });
  }

  /* ---------------- shelf ---------------- */

  function makeCard(meta, isLocal) {
    const btn = document.createElement('button');
    btn.className = 'card';
    btn.type = 'button';

    const cover = document.createElement('div');
    cover.className = 'cover';

    if (meta.coverSrc) {
      const img = document.createElement('img');
      img.loading = 'lazy';
      img.alt = '';
      img.src = meta.coverSrc;
      img.onerror = () => { img.remove(); addFallback(); };
      cover.appendChild(img);
    } else {
      addFallback();
    }

    function addFallback() {
      const f = document.createElement('div');
      f.className = 'fallback';
      f.textContent = meta.title;
      cover.appendChild(f);
    }

    const pct = pctOf(meta);
    if (pct > 0) {
      const prog = document.createElement('div');
      prog.className = 'prog';
      const i = document.createElement('i');
      i.style.width = pct + '%';
      prog.appendChild(i);
      cover.appendChild(prog);
    }

    if (isLocal) {
      const del = document.createElement('button');
      del.className = 'del';
      del.type = 'button';
      del.textContent = '\u00d7';
      del.setAttribute('aria-label', 'Remove book');
      del.addEventListener('click', async (e) => {
        e.stopPropagation();
        if (!confirm('Remove "' + meta.title + '" from this device?')) return;
        await idbDel(meta.id);
        await loadLocal();
        renderShelf();
      });
      cover.appendChild(del);
    }

    const t = document.createElement('div');
    t.className = 't';
    t.textContent = meta.title;

    const a = document.createElement('div');
    a.className = 'a';
    a.textContent = meta.author || '';

    const lv = document.createElement('span');
    lv.className = 'lv';
    lv.textContent = meta.level || 'Book';

    btn.append(cover, t, a, lv);
    btn.addEventListener('click', () => openBook(meta, isLocal));
    return btn;
  }

  function matchesFilter(meta) {
    const lv = meta.level || '';
    if (state.filter === 'all') return true;
    if (state.filter === 'picture') return lv === 'Picture book';
    if (state.filter === 'early') return /Grade 3|Grade 4\b/.test(lv);
    if (state.filter === 'stretch') return /Grade 5|Grade 6|Grade 7|Grade 8/.test(lv);
    return true;
  }

  function renderShelf() {
    shelfEl.innerHTML = '';
    const list = state.index.filter(matchesFilter);
    if (!list.length) {
      const p = document.createElement('p');
      p.className = 'hint';
      p.textContent = 'No books in this shelf yet.';
      p.style.padding = '0 22px';
      shelfEl.appendChild(p);
    }
    for (const meta of list) {
      shelfEl.appendChild(makeCard(meta, false));
    }

    mineEl.innerHTML = '';
    for (const meta of state.local) {
      mineEl.appendChild(makeCard(meta, true));
    }
    mineSection.classList.toggle('hidden', state.local.length === 0);

    renderContinue();
  }

  function renderContinue() {
    const all = [...state.local, ...state.index];
    let best = null;
    for (const m of all) {
      const p = getProgress(m.id);
      if (p && p.ts && (!best || p.ts > best.p.ts)) best = { m, p };
    }
    if (!best || !best.p.page) {
      continueBanner.classList.add('hidden');
      return;
    }
    const pct = Math.round(((best.p.page + 1) / best.p.total) * 100);
    continueBanner.innerHTML = '';
    if (best.m.coverSrc) {
      const img = document.createElement('img');
      img.src = best.m.coverSrc;
      img.alt = '';
      continueBanner.appendChild(img);
    }
    const txt = document.createElement('div');
    txt.className = 'c-txt';
    const lab = document.createElement('div');
    lab.className = 'c-label';
    lab.textContent = 'Continue reading';
    const ti = document.createElement('div');
    ti.className = 'c-title';
    ti.textContent = best.m.title + ' \u00b7 ' + pct + '%';
    txt.append(lab, ti);
    continueBanner.appendChild(txt);
    continueBanner.classList.remove('hidden');
    continueBanner.onclick = () => openBook(best.m, state.local.some((l) => l.id === best.m.id));
  }

  function buildFilters() {
    const wrap = $('#filters');
    const defs = [
      ['all', 'All books'],
      ['picture', 'Picture books'],
      ['early', 'Early readers'],
      ['stretch', 'Stretch'],
    ];
    wrap.innerHTML = '';
    for (const [key, label] of defs) {
      const b = document.createElement('button');
      b.className = 'chip';
      b.type = 'button';
      b.textContent = label;
      b.setAttribute('aria-pressed', String(state.filter === key));
      b.addEventListener('click', () => {
        state.filter = key;
        for (const c of wrap.children) c.setAttribute('aria-pressed', String(c.textContent === label));
        renderShelf();
      });
      wrap.appendChild(b);
    }
  }

  /* ---------------- reader ---------------- */

  function revokeUrls() {
    for (const u of state.objectUrls) URL.revokeObjectURL(u);
    state.objectUrls = [];
  }

  function applySettings() {
    document.documentElement.style.setProperty('--page-size', settings.size + 'rem');
    document.body.classList.toggle('night', !!settings.night);
    localStorage.setItem(K_SET, JSON.stringify(settings));
  }

  async function openBook(meta, isLocal) {
    let bookData;
    let basePath = '';

    if (isLocal) {
      const rec = await idbGet(meta.id);
      if (!rec) return;
      bookData = {
        title: rec.title,
        author: rec.author,
        pages: rec.pages.map((p) => ({ text: p.text || '' })),
      };
      basePath = '';
    } else {
      const res = await fetch('books/' + meta.id + '/book.json');
      if (!res.ok) { alert('Could not load this book.'); return; }
      bookData = await res.json();
      basePath = 'books/' + meta.id + '/';
    }

    state.book = bookData;
    state.meta = meta;
    state.restoreTo = 0;
    state.userScrolled = false;
    const saved = getProgress(meta.id);
    if (saved && saved.page) state.restoreTo = saved.page;
    if (typeof state.forcePage === 'number' && !isNaN(state.forcePage)) {
      state.restoreTo = state.forcePage;
      state.forcePage = null;
    }

    pagesEl.innerHTML = '';
    revokeUrls();

    // cover page
    const coverPage = document.createElement('section');
    coverPage.className = 'page page-cover';
    let coverSrc = meta.coverSrc;
    if (isLocal && meta.coverBlob) {
      coverSrc = URL.createObjectURL(meta.coverBlob);
      state.objectUrls.push(coverSrc);
    }
    if (coverSrc) {
      const img = document.createElement('img');
      img.src = coverSrc;
      img.alt = '';
      coverPage.appendChild(img);
    }
    const h2 = document.createElement('h2');
    h2.textContent = bookData.title;
    const by = document.createElement('div');
    by.className = 'by';
    by.textContent = bookData.author || '';
    coverPage.append(h2, by);
    pagesEl.appendChild(coverPage);

    // pages
    bookData.pages.forEach((p, i) => {
      const sec = document.createElement('section');
      sec.className = 'page';
      sec.dataset.i = String(i);

      if (p.image) {
        const fig = document.createElement('figure');
        const img = document.createElement('img');
        img.loading = i < 3 ? 'eager' : 'lazy';
        img.decoding = 'async';
        img.alt = '';
        if (isLocal && p.blob) {
          const u = URL.createObjectURL(p.blob);
          state.objectUrls.push(u);
          img.src = u;
          img.onload = maybeRestore;
        } else {
          img.src = basePath + p.image;
          img.onload = maybeRestore;
        }
        fig.appendChild(img);
        sec.appendChild(fig);
      }

      if (p.text) {
        const para = document.createElement('p');
        if (i === 0) para.className = 'drop';
        para.textContent = p.text;
        sec.appendChild(para);
      }

      const num = document.createElement('div');
      num.className = 'num';
      num.textContent = String(i + 1);
      sec.appendChild(num);

      pagesEl.appendChild(sec);
    });

    state.total = bookData.pages.length;

    $('#reader-title').textContent = bookData.title;
    $('#reader-sub').textContent = (bookData.author || '') + ' \u00b7 ' + state.total + ' pages';

    shelfView.classList.add('hidden');
    readerView.classList.remove('hidden');
    state.ignoreScrollUntil = Date.now() + 900;
    state.userScrolled = false;
    window.scrollTo(0, 0);
    readerBar.classList.remove('hide');

    updateProgressUI();
    if (state.restoreTo) {
      pagesEl.querySelectorAll('img').forEach((im) => {
        if (im.complete) return;
        im.addEventListener('load', maybeRestore, { once: true });
      });
      setTimeout(maybeRestore, 80);
      setTimeout(maybeRestore, 500);
    }
  }

  function maybeRestore() {
    if (!state.restoreTo || state.userScrolled) return;
    const target = pagesEl.querySelector('.page[data-i="' + state.restoreTo + '"]');
    if (!target) return;
    const y = target.getBoundingClientRect().top + window.scrollY - 84;
    window.scrollTo(0, y);
  }

  function closeBook() {
    if (state.meta) saveProgress(state.meta.id, state.current, state.total);
    state.book = null;
    state.meta = null;
    state.total = 0;
    state.current = 0;
    pagesEl.innerHTML = '';
    revokeUrls();
    readerView.classList.add('hidden');
    shelfView.classList.remove('hidden');
    window.scrollTo(0, 0);
    renderShelf();
  }

  function currentPageIndex() {
    const pages = pagesEl.querySelectorAll('.page[data-i]');
    if (!pages.length) return 0;
    const anchor = 110;
    let best = 0;
    for (const el of pages) {
      const top = el.getBoundingClientRect().top;
      if (top <= anchor) best = Number(el.dataset.i);
      else break;
    }
    return best;
  }

  function updateProgressUI() {
    const max = document.documentElement.scrollHeight - window.innerHeight;
    const frac = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0;
    progressFill.style.width = (frac * 100).toFixed(1) + '%';
    pagePill.textContent = (state.current + 1) + ' / ' + (state.total || 1);
  }

  let saveTimer = null;
  let lastY = 0;
  window.addEventListener('scroll', () => {
    if (readerView.classList.contains('hidden')) return;
    if (Date.now() < (state.ignoreScrollUntil || 0)) return;
    state.userScrolled = true;
    state.current = currentPageIndex();
    updateProgressUI();

    const y = window.scrollY;
    if (y > lastY + 8 && y > 140) readerBar.classList.add('hide');
    else if (y < lastY - 8) readerBar.classList.remove('hide');
    lastY = y;

    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      if (state.meta) saveProgress(state.meta.id, state.current, state.total);
    }, 400);
  }, { passive: true });

  window.addEventListener('keydown', (e) => {
    if (readerView.classList.contains('hidden')) return;
    if (e.key === 'ArrowDown' || e.key === ' ') {
      window.scrollBy({ top: window.innerHeight * 0.85, behavior: 'smooth' });
    } else if (e.key === 'ArrowUp') {
      window.scrollBy({ top: -window.innerHeight * 0.85, behavior: 'smooth' });
    } else if (e.key === 'Escape') {
      closeBook();
    }
  });

  /* ---------------- add book ---------------- */

  let pendingFiles = [];

  function openModal() {
    $('#add-modal').classList.remove('hidden');
    $('#m-title').value = '';
    $('#m-author').value = '';
    $('#m-count').textContent = '';
    $('#m-save').disabled = true;
    pendingFiles = [];
  }

  function closeModal() {
    $('#add-modal').classList.add('hidden');
  }

  async function savePending() {
    const title = $('#m-title').value.trim() || 'My book';
    const author = $('#m-author').value.trim();
    const pages = pendingFiles.map((f) => ({ blob: f, text: '' }));
    const rec = {
      id: 'local-' + Date.now().toString(36),
      title,
      author,
      cover: pendingFiles[0] || null,
      pages,
      created: Date.now(),
    };
    await idbPut(rec);
    closeModal();
    await loadLocal();
    renderShelf();
  }

  /* ---------------- boot ---------------- */

  async function loadLocal() {
    try {
      const recs = await idbAll();
      state.local = recs.map((r) => ({
        id: r.id,
        title: r.title,
        author: r.author,
        level: 'My book',
        coverBlob: r.cover || null,
        coverSrc: r.cover ? URL.createObjectURL(r.cover) : null,
      }));
    } catch (e) {
      state.local = [];
      document.documentElement.dataset.idberror = String(e && e.message);
    }
  }

  async function boot() {
    applySettings();
    buildFilters();

    try {
      const res = await fetch('books/index.json', { cache: 'no-cache' });
      if (!res.ok) throw new Error('index ' + res.status);
      state.index = await res.json();
      for (const m of state.index) m.coverSrc = m.cover;
    } catch (e) {
      state.index = [];
      document.documentElement.dataset.ixerror = String(e && e.message);
    }

    renderShelf();
    openFromHash();

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('sw.js').catch(() => {});
    }

    // local books load in the background so a slow IndexedDB never blocks the shelf
    loadLocal().then(() => renderShelf());
  }

  function openFromHash() {
    const m = location.hash.match(/^#book\/([^/]+)(?:\/(\d+))?$/);
    if (!m) return;
    const id = decodeURIComponent(m[1]);
    if (m[2]) state.forcePage = Number(m[2]);
    const local = state.local.find((b) => b.id === id);
    if (local) { openBook(local, true); return; }
    const meta = state.index.find((b) => b.id === id);
    if (meta) openBook(meta, false);
  }

  /* ---------------- wiring ---------------- */

  $('#back-btn').addEventListener('click', closeBook);
  $('#theme-btn').addEventListener('click', () => {
    settings.night = !settings.night;
    applySettings();
  });
  $('#font-up').addEventListener('click', () => {
    settings.size = Math.min(2.0, +(settings.size + 0.12).toFixed(2));
    applySettings();
  });
  $('#font-down').addEventListener('click', () => {
    settings.size = Math.max(0.9, +(settings.size - 0.12).toFixed(2));
    applySettings();
  });
  upBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

  $('#add-btn').addEventListener('click', openModal);
  $('#m-cancel').addEventListener('click', closeModal);
  $('#m-pick').addEventListener('click', () => $('#m-files').click());
  $('#m-files').addEventListener('change', (e) => {
    const files = Array.from(e.target.files || []).filter((f) => f.type.startsWith('image/'));
    files.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
    pendingFiles = files;
    $('#m-count').textContent = files.length
      ? files.length + ' pages ready. They will be kept on this device only.'
      : 'No images picked yet.';
    if (files.length && !$('#m-title').value) {
      $('#m-title').value = files[0].name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ').trim();
    }
    $('#m-save').disabled = files.length === 0;
  });
  $('#m-save').addEventListener('click', savePending);

  boot().catch((e) => {
    document.documentElement.dataset.booterror = String((e && e.message) || e) + ' | ' + String((e && e.stack) || '').split('\n').slice(0, 3).join(' ');
  });
})();
