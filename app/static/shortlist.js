(function () {
  'use strict';
  const KEY = 'njtbids.shortlist.v1';
  const LIMIT = 200;
  function read(storage) {
    const raw = storage.getItem(KEY);
    if (!raw) return [];
    const ids = JSON.parse(raw);
    if (!Array.isArray(ids) || ids.some(id => typeof id !== 'string' || !id || id.length > 160)) {
      throw new Error('Invalid shortlist data');
    }
    return [...new Set(ids)].slice(0, LIMIT);
  }
  function toggle(storage, id) {
    const ids = read(storage);
    const saved = ids.includes(id);
    if (!saved && ids.length >= LIMIT) throw new Error('Shortlist full (200 notices). Remove one first.');
    storage.setItem(KEY, JSON.stringify(saved ? ids.filter(value => value !== id) : [...ids, id]));
    return !saved;
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {read, toggle, KEY};
  if (typeof document === 'undefined') return;
  const message = document.getElementById('shortlist-message');
  const results = document.getElementById('shortlist-results');
  const recordsElement = document.getElementById('shortlist-records');
  const records = recordsElement ? JSON.parse(recordsElement.textContent) : [];
  const byId = new Map(records.map(record => [record.id, record]));
  function say(text) { message.textContent = text; }
  function refresh() {
    const ids = read(window.localStorage);
    if (results) {
      results.replaceChildren();
      if (!ids.length) {
        const empty = document.createElement('p');
        empty.textContent = 'No saved opportunities yet. Use Save to shortlist on any opportunity.';
        results.append(empty);
      }
      for (const id of ids) {
        const record = byId.get(id);
        const card = document.createElement('article');
        card.className = 'shortlist-card';
        const heading = document.createElement('h2');
        if (record) {
          const link = document.createElement('a');
          link.href = record.url;
          link.textContent = record.title;
          heading.append(link);
        } else heading.textContent = 'Saved notice no longer available in the index';
        const facts = document.createElement('p');
        facts.textContent = record ? `${record.agency} | ${record.status} | ${record.deadline}${record.timing_note ? ' | ' + record.timing_note : ''}` : `Reference: ${id}. Removal does not establish cancellation.`;
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'shortlist-save';
        button.dataset.shortlistId = id;
        card.append(heading, facts, button);
        results.append(card);
      }
    }
    document.querySelectorAll('[data-shortlist-id]').forEach(button => {
      const saved = ids.includes(button.dataset.shortlistId);
      button.hidden = false;
      button.textContent = saved ? 'Remove from shortlist' : 'Save to shortlist';
      button.setAttribute('aria-pressed', String(saved));
    });
  }
  document.addEventListener('click', event => {
    const button = event.target.closest('[data-shortlist-id]');
    if (!button) return;
    try {
      const saved = toggle(window.localStorage, button.dataset.shortlistId);
      refresh();
      say(saved ? 'Saved in this browser.' : 'Removed from shortlist.');
      if (results) message.focus();
    } catch (error) {
      say(error.message.startsWith('Shortlist full') ? error.message : 'Could not save. Browser storage may be blocked or saved data may be damaged. Your existing shortlist was not overwritten.');
    }
  });
  window.addEventListener('storage', event => {
    if (event.key === KEY || event.key === null) {
      try { refresh(); } catch (_) { say('Could not read saved data in this browser.'); }
    }
  });
  try { refresh(); } catch (_) {
    say('Shortlist unavailable: browser storage is blocked or saved data is damaged.');
  }
}());
