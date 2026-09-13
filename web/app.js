const view = document.getElementById('view');

// ---------- app state ----------
//
// Runs live here rather than inside a page's closure. A parse or extraction takes minutes,
// people switch tabs while it runs, and a run that only exists inside the page that started
// it dies (or worse, keeps writing into a DOM that has been replaced) the moment they do.
const state = {
  generation: 0,   // bumped per navigation; async work checks it before painting anything
  run: null,       // {stage, items:[{label,state,message}], finished}
  timings: {},     // /api/timings, for "about how long will this take"
};

// ---------- tiny helpers ----------

async function errorMessage(res) {
  let body;
  try { body = await res.json(); } catch { return res.statusText; }
  const d = body && body.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d)) return d.map(e => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; ');
  return res.statusText;
}

async function api(path, opts) {
  const res = await fetch(path, opts && {
    ...opts,
    headers: opts.body instanceof FormData ? undefined : { 'Content-Type': 'application/json', ...(opts.headers || {}) },
  });
  if (!res.ok) throw new Error(await errorMessage(res));
  return res.status === 204 ? null : res.json();
}
const get = (path) => api(path);
const put = (path, body) => api(path, { method: 'PUT', body: JSON.stringify(body) });
const post = (path, body) => api(path, { method: 'POST', body: body instanceof FormData ? body : JSON.stringify(body) });
const del = (path) => api(path, { method: 'DELETE' });

const esc = (s) => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = (v) => (v === null || v === undefined || v === '') ? '<span class="null">&mdash;</span>' : esc(v);
const blank = (v) => v === null || v === undefined || v === '';

function el(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

const costOf = (r) => (r.usage && r.usage.cost_usd) ? ` · ${money(r.usage.cost_usd)}` : '';
const money = (n) => !n ? '—' : n < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
const tokens = (n) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);

// litellm prices the public models; it cannot price a private deployment, and there a dollar
// figure of zero would read as "free" for calls that were actually billed. Fall back to the
// token count, which is always real, and say which one is being shown.
function spendCell(cost, tok) {
  if (cost) return `<td class="money" title="${tok ? tokens(tok) + ' tokens' : ''}">${money(cost)}</td>`;
  if (tok) return `<td class="money unpriced" title="this model has no public price; tokens are exact">${tokens(tok)} tok</td>`;
  return '<td class="money muted">—</td>';
}

function humanSeconds(s) {
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  return `${m}m ${Math.round(s - m * 60)}s`;
}

// "about how long will this take", from this machine's own history -- never a hardcoded guess,
// because parse speed depends on the PDF, on OCR, and on whether there's a GPU.
// A 4 MB paper takes proportionally longer than a 0.5 MB one, and the browser knows the size
// before it uploads -- so the estimate is per byte rather than a flat median over past parses.
function parseEta(file) {
  const t = state.timings.parse;
  if (!t) return null;
  return (t.unit === 'bytes' && t.per_unit) ? t.per_unit * file.size : t.seconds;
}

function etaText(stage, size) {
  const t = state.timings[stage];
  if (!t) return 'no estimate yet — this is the first run of this stage';
  const seconds = (t.per_unit && size) ? t.per_unit * size : t.seconds;
  return `about ${humanSeconds(seconds)} expected (median of the last ${t.n})`;
}

// ---------- run engine: one item at a time, visible from every tab ----------

function runIsActive() { return state.run && !state.run.finished; }

async function runJob(stage, items, runOne) {
  state.run = {
    stage,
    items: items.map(i => ({ label: i.label, state: 'queued', message: '', eta: i.eta || null })),
    finished: false,
    stopping: false,
  };
  paintRun();
  for (let i = 0; i < items.length; i++) {
    // Stop means "after this paper". The request in flight is already costing money at the
    // provider, and abandoning it would leave a half-written result nobody could see.
    if (state.run.stopping) {
      for (let j = i; j < items.length; j++) {
        state.run.items[j].state = 'skipped';
        state.run.items[j].message = 'not run';
      }
      break;
    }
    const started = Date.now();
    state.run.items[i].state = 'running';
    state.run.items[i].startedAt = started;
    paintRun();
    const ticker = setInterval(paintRun, 1000);   // so "running" visibly counts up, not just spins
    try {
      state.run.items[i].message = (await runOne(items[i], state.run.items[i])) || 'done';
      state.run.items[i].state = 'ok';
    } catch (e) {
      state.run.items[i].message = e.message;
      state.run.items[i].state = 'failed';
    }
    clearInterval(ticker);
    state.run.items[i].seconds = (Date.now() - started) / 1000;
    paintRun();
  }
  state.run.finished = true;
  paintRun();
  state.timings = await get('/api/timings').catch(() => state.timings);
  return state.run;
}

function runHTML(run) {
  const done = run.items.filter(i => i.state === 'ok' || i.state === 'failed').length;
  const failed = run.items.filter(i => i.state === 'failed').length;
  const elapsed = run.items.reduce((n, i) => n + (i.seconds || 0), 0)
    + (run.items.find(i => i.state === 'running')?.startedAt ? (Date.now() - run.items.find(i => i.state === 'running').startedAt) / 1000 : 0);
  const remaining = run.items.filter(i => i.state === 'queued' || i.state === 'running')
    .reduce((n, i) => n + (i.eta || 0), 0);
  const clock = run.finished
    ? `total ${humanSeconds(elapsed)}`
    : `${humanSeconds(elapsed)} elapsed${remaining ? ` · about ${humanSeconds(remaining)} left` : ''}`;
  const rows = run.items.map(item => {
    const elapsed = item.state === 'running' && item.startedAt
      ? ` (${humanSeconds((Date.now() - item.startedAt) / 1000)}${item.eta ? ' of ~' + humanSeconds(item.eta) : ''})`
      : '';
    const detail = item.state === 'queued'
      ? (item.eta ? `queued · ~${humanSeconds(item.eta)}` : 'queued')
      : item.state === 'running' ? `running${elapsed}` : item.message;
    return `<div class="status-row ${item.state}">
      <span class="spinner" ${item.state === 'running' ? '' : 'hidden'}></span>
      <span class="name" title="${esc(item.label)}">${esc(item.label)}</span>
      <span class="state">${esc(detail)}</span>
    </div>`;
  }).join('');
  const spent = run.items.reduce((n, i) => n + (i.cost || 0), 0);
  return `<div class="row runsummary">
      <span class="bar"><i style="width:${100 * done / run.items.length}%"></i></span>
      <span>${done} / ${run.items.length}${failed ? ` · ${failed} failed` : ''}</span>
      <span class="sep">${clock}</span>
      ${spent ? `<span class="sep">$${spent.toFixed(4)}</span>` : ''}
      <span class="grow"></span>
      ${run.finished ? '' : `<button id="run-stop" ${run.stopping ? 'disabled' : ''}>
        ${run.stopping ? 'stopping after this one…' : 'Stop'}</button>`}
    </div>
    <div class="statuslist">${rows}</div>`;
}

// The banner is in the header, so a run stays visible (and legible) from whichever tab you
// wander onto -- the answer to "can I leave this page?" is yes, and this is what says so.
function paintRun() {
  const banner = document.getElementById('run-banner');
  const r = state.run;
  if (!r) { banner.hidden = true; return; }
  const done = r.items.filter(i => i.state === 'ok' || i.state === 'failed').length;
  const failed = r.items.filter(i => i.state === 'failed').length;
  banner.hidden = false;
  banner.className = 'runbanner' + (r.finished ? (failed ? ' failed' : ' done') : '');
  const current = r.items.find(i => i.state === 'running');
  banner.innerHTML = r.finished
    ? `${esc(r.stage)} finished — ${done - failed} ok${failed ? `, ${failed} failed` : ''}
       <button class="linkish" id="run-dismiss">dismiss</button>`
    : `<span class="spinner"></span> ${esc(r.stage)} ${done}/${r.items.length}
       <span class="muted">${esc(current ? current.label : '')}</span>`;
  const dismiss = document.getElementById('run-dismiss');
  if (dismiss) dismiss.onclick = () => { state.run = null; paintRun(); };

  const host = document.getElementById('run-progress');
  if (host) {
    host.innerHTML = runHTML(r);
    const stop = document.getElementById('run-stop');
    if (stop) stop.onclick = () => { state.run.stopping = true; paintRun(); };
  }
}

// ---------- router ----------

const routes = { parse: renderParse, extract: renderExtract, judge: renderJudge,
                 report: renderReport, settings: renderSettings };

async function router() {
  const gen = ++state.generation;
  const name = (location.hash.replace('#/', '') || 'parse');
  document.querySelectorAll('nav a').forEach(a => a.classList.toggle('active', a.getAttribute('href') === '#/' + name));
  view.innerHTML = '<section><p class="muted">Loading&hellip;</p></section>';
  try {
    await (routes[name] || renderParse)(gen);
  } catch (e) {
    if (gen === state.generation) view.innerHTML = `<section class="panel error">${esc(e.message)}</section>`;
  }
}
const stale = (gen) => gen !== state.generation;

window.addEventListener('hashchange', router);
window.addEventListener('beforeunload', (e) => {
  if (runIsActive()) { e.preventDefault(); e.returnValue = ''; }
});

// ---------- review pane: text on the left, records on the right ----------

const review = {
  paperId: null, chunks: [], sourceTracking: true, schema: [],
  records: [], modelRecords: [], notes: {}, verdicts: null,
  selected: null,        // record whose source chunks are highlighted
  key: null, marks: [], markIndex: -1,
  editing: new Set(), undo: new Map(), dirty: false,
};

const RX_SPECIAL = /[.*+?^${}()|[\]\\]/g;

function valueForms(v) {
  if (blank(v)) return [];
  if (typeof v !== 'number') {
    const s = String(v);
    return s.length > 1 ? [s] : [];
  }
  const out = new Set([String(v)]);
  if (!Number.isInteger(v)) out.add(v.toFixed(1).replace(/\.0$/, ''));
  return [...out];
}

// Marks every occurrence of one value inside already-rendered HTML, walking text nodes only so
// a match can never land inside a tag or break a table. docling splits decimals across line
// breaks ("42. 7"), so whitespace around a literal dot is allowed room in the pattern.
function markValue(pane, value) {
  const forms = valueForms(value).sort((a, b) => b.length - a.length);
  if (!forms.length) return [];
  const source = '(^|[^\\w.])(' + forms.map(s =>
    s.replace(RX_SPECIAL, '\\$&').replace(/\\\./g, '\\s*\\.\\s*')).join('|') + ')(?![\\w.])';
  const rx = new RegExp(source, 'gi');
  const walker = document.createTreeWalker(pane, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    if (!new RegExp(source, 'i').test(node.nodeValue)) continue;
    const span = document.createElement('span');
    span.innerHTML = esc(node.nodeValue).replace(rx, (m, pre, hit) => pre + '<mark>' + hit + '</mark>');
    node.parentNode.replaceChild(span, node);
  }
  return [...pane.querySelectorAll('mark')];
}

function textPane() { return document.getElementById('text-pane'); }

// One painter for the left pane: chunk HTML (markdown, so tables render as tables), the
// selected record's cited chunks shaded, and optionally one value marked throughout. Both
// signals have to be applied in the same pass -- painting them separately meant whichever ran
// second wiped the first.
function paintText(valueToMark) {
  const pane = textPane();
  if (!pane) return;
  const cited = new Set(review.selected !== null
    ? (review.records[review.selected]?.source_chunk_ids || []) : []);
  pane.innerHTML = review.chunks.map(c =>
    `<div class="chunk${cited.has(c.id) ? ' cited' : ''}" data-id="${c.id}">` +
    (review.sourceTracking ? `<span class="cid">${c.id.slice(0, 8)}</span>` : '') +
    c.html + '</div>').join('') || '<p class="muted">no text</p>';
  review.marks = blank(valueToMark) ? [] : markValue(pane, valueToMark);
}

function selectRecord(i) {
  review.selected = i;
  review.key = null;
  review.markIndex = -1;
  paintText(null);
  paintRecords();
  const first = textPane().querySelector('.chunk.cited');
  if (first) first.scrollIntoView({ behavior: 'smooth', block: 'center' });
  else if ((review.records[i]?.source_chunk_ids || []).length === 0) flashNote('this record cites no source chunks');
  else flashNote('the chunks this record cites are not in this paper\'s text');
}

// Click a field once to mark every occurrence of its value; click it again to walk to the next.
function cycleField(i, field, value) {
  if (review.selected !== i) { review.selected = i; review.key = null; }
  const key = `${i}::${field}::${String(value)}`;
  if (review.key !== key) {
    review.key = key;
    review.markIndex = -1;
    paintText(value);
    paintRecords();
  }
  if (!review.marks.length) { flashNote(`"${value}" does not appear in this paper's text`); return; }
  review.marks.forEach(m => m.classList.remove('current'));
  review.markIndex = (review.markIndex + 1) % review.marks.length;
  const m = review.marks[review.markIndex];
  m.classList.add('current');
  m.scrollIntoView({ behavior: 'smooth', block: 'center' });
  const counter = document.getElementById('match-counter');
  if (counter) counter.textContent = `${field} = ${value} — match ${review.markIndex + 1} of ${review.marks.length}`;
}

function flashNote(text) {
  const pane = textPane();
  if (!pane) return;
  const note = el(`<div class="nomatch">${esc(text)}</div>`);
  pane.prepend(note);
  setTimeout(() => note.remove(), 2200);
}

function typeOf(field) {
  return (review.schema.find(f => f.name === field) || {}).type || 'string';
}

function coerce(field, raw) {
  if (raw === '') return null;
  const t = typeOf(field);
  if (t === 'number' || t === 'integer') {
    const n = Number(raw);
    if (Number.isNaN(n)) throw new Error(`${field}: "${raw}" is not a number`);
    return t === 'integer' ? Math.round(n) : n;
  }
  if (t === 'boolean') return raw === 'true';
  return raw;
}

function isEdited(i) {
  const a = review.records[i], b = review.modelRecords[i];
  if (!b) return false;
  return Object.keys({ ...a, ...b }).some(k => k !== 'source_chunk_ids' && String(a[k] ?? '') !== String(b[k] ?? ''));
}

function recordCardHTML(rec, i) {
  const v = review.verdicts ? review.verdicts.get(i) : null;
  const note = review.notes[i] || {};
  const editing = review.editing.has(i);
  const cites = (rec.source_chunk_ids || []).length;
  const bad = new Set(v ? (v.bad_fields || []) : []);

  // The judge's proposal for a field is rendered inside that field, not in a list underneath:
  // "0.25 struck, 5 proposed, apply" reads in one glance, where a separate block made the eye
  // carry a field name back and forth across the card.
  const fixes = new Map((v ? v.fixes || [] : []).map((fx, fi) => [fx.field, { ...fx, fi }]));

  const cells = Object.entries(rec).filter(([f]) => f !== 'source_chunk_ids').map(([f, val]) => {
    if (editing) {
      const t = typeOf(f);
      const input = t === 'boolean'
        ? `<select data-edit="${esc(f)}"><option value="">&mdash;</option>
             <option value="true" ${val === true ? 'selected' : ''}>true</option>
             <option value="false" ${val === false ? 'selected' : ''}>false</option></select>`
        : `<input data-edit="${esc(f)}" value="${blank(val) ? '' : esc(val)}"
             ${t === 'number' || t === 'integer' ? 'inputmode="decimal"' : ''}>`;
      return `<div class="cell editing"><k>${esc(f)}</k>${input}</div>`;
    }
    const fix = fixes.get(f);
    // "Already applied" is read off the data, not off a flag we set when the button was
    // pressed: that way it still reads correctly after a save and a reload, and undo works in
    // a later session too.
    const applied = fix && String(val ?? '') === String(fix.value ?? '');
    const body = !fix
      ? `<v>${fmt(val)}</v>`
      : applied
        ? `<div class="fixline applied">
             <span class="to" data-find="${esc(fix.value ?? '')}" data-field="${esc(f)}">${fmt(val)}</span>
             <span class="tag applied">judge's value</span>
             <button class="undo" data-undo="${esc(f)}"
               title="put back what the extractor wrote">undo</button>
           </div>`
        : `<div class="fixline">
             <span class="was">${blank(val) ? '&mdash;' : esc(val)}</span>
             <span class="arrow">&rarr;</span>
             <span class="to" data-find="${esc(fix.value ?? '')}" data-field="${esc(f)}"
                   title="${esc(fix.evidence || 'click to find this value in the text')}">${fmt(fix.value)}</span>
             <button class="apply" data-apply="${fix.fi}" title="write the judge's value into this record">apply</button>
           </div>`;
    return `<div class="cell${bad.has(f) ? ' bad' : ''}${fix ? (applied ? ' applied' : ' proposed') : ''}"
       data-field="${esc(f)}"
       title="click to find this value in the text, click again for the next match">
       <k>${esc(f)}</k>${body}</div>`;
  }).join('');

  const badge = v ? `<span class="badge ${v.verdict}">${v.verdict}</span>` : '';
  const dropTag = v && v.drop_record ? '<span class="tag no">judge would drop this</span>' : '';
  const editedTag = isEdited(i) ? '<span class="tag edit">edited</span>' : '';
  // A verdict describes the values the judge was shown. Once a reviewer changes one, the
  // verdict is about the old record, and saying so is cheaper than silently implying it still
  // holds -- the judge would have to be re-run for that.
  const staleTag = (v && isEdited(i))
    ? '<span class="tag stale" title="the judge saw the earlier values; re-run it to re-check">verdict predates this edit</span>'
    : '';
  const flagged = bad.size ? `${bad.size} field${bad.size === 1 ? '' : 's'} flagged` : 'no fields flagged';
  const evidence = [...fixes.values()].filter(fx => fx.evidence)
    .map(fx => `<span class="ev"><b>${esc(fx.field)}</b>: ${esc(fx.evidence)}</span>`).join('');
  const reasoning = v && (v.critique || evidence) ? `
    <details class="reasoning"><summary>judge's reasoning &middot; ${flagged}</summary>
      <div class="body">${esc(v.critique || '')}${evidence}</div></details>` : '';

  return `<div class="rec${review.selected === i ? ' on' : ''}" data-i="${i}">
    <div class="rechead">
      <b>#${i}</b> ${badge} ${dropTag} ${editedTag} ${staleTag}
      <span class="muted">${cites} cited chunk${cites === 1 ? '' : 's'}</span>
      <span class="grow"></span>
      ${editing
        ? `<button class="primary" data-save="${i}">Save</button><button data-cancel="${i}">Cancel</button>`
        : `<button data-edit-toggle="${i}">Edit</button>`}
    </div>
    <div class="grid">${cells}</div>
    ${reasoning}
    <div class="feedback">
      <button class="flag ok ${note.flag === 'ok' ? 'on' : ''}" data-flag="ok" data-i="${i}">looks right</button>
      <button class="flag bad ${note.flag === 'bad' ? 'on' : ''}" data-flag="bad" data-i="${i}">looks wrong</button>
      <input class="note" data-note="${i}" placeholder="note for this record (optional)"
             value="${esc(note.note || '')}">
    </div>
  </div>`;
}

function paintRecords() {
  const host = document.getElementById('rec-pane');
  if (!host) return;
  host.innerHTML = review.records.length
    ? review.records.map((r, i) => recordCardHTML(r, i)).join('')
    : `<div class="empty-records">
         <b>The model returned no records for this paper.</b>
         <p>That is usually one of three things, in this order of likelihood:</p>
         <ol>
           <li>The paper is <b>out of scope</b> for your prompt &mdash; it is about something your
               schema does not describe. Read the text on the left and see.</li>
           <li>Your prompt's <b>SKIP rules are too broad</b> and excluded everything.</li>
           <li>The paper <b>parsed badly</b> &mdash; if the text on the left looks empty or
               scrambled, that is the problem, not the model.</li>
         </ol>
         <p class="muted">It is not an error, and it did cost a call. Nothing is wrong with the
           app if a paper genuinely has nothing to extract.</p>
       </div>`;
  wireRecords(host);
  const save = document.getElementById('save-review');
  if (save) save.disabled = !review.dirty;
}

function wireRecords(host) {
  host.querySelectorAll('.rec').forEach(card => {
    const i = Number(card.dataset.i);
    card.addEventListener('click', (e) => {
      if (e.target.closest('button, input, select, .cell')) return;
      selectRecord(i);
    });
    card.querySelectorAll('.cell[data-field]').forEach(cell => {
      const field = cell.dataset.field;
      cell.addEventListener('click', (e) => {
        if (e.target.closest('button, .to')) return;   // those have their own meaning
        const value = review.records[i][field];
        if (blank(value)) { flashNote(`${field} is empty in this record`); return; }
        cycleField(i, field, value);
      });
    });
    const toggle = card.querySelector('[data-edit-toggle]');
    if (toggle) toggle.addEventListener('click', () => { review.editing.add(i); paintRecords(); });
    const cancel = card.querySelector('[data-cancel]');
    if (cancel) cancel.addEventListener('click', () => { review.editing.delete(i); paintRecords(); });
    const save = card.querySelector('[data-save]');
    if (save) save.addEventListener('click', () => {
      try {
        card.querySelectorAll('[data-edit]').forEach(input => {
          review.records[i][input.dataset.edit] = coerce(input.dataset.edit, input.value.trim());
        });
      } catch (err) { flashNote(err.message); return; }
      review.editing.delete(i);
      review.dirty = true;
      paintRecords();
    });
    card.querySelectorAll('[data-apply]').forEach(btn => btn.addEventListener('click', () => {
      const fix = review.verdicts.get(i).fixes[Number(btn.dataset.apply)];
      review.undo.set(`${i}::${fix.field}`, review.records[i][fix.field]);   // what it was
      review.records[i][fix.field] = fix.value;
      review.dirty = true;
      paintRecords();
    }));
    card.querySelectorAll('[data-undo]').forEach(btn => btn.addEventListener('click', () => {
      const field = btn.dataset.undo;
      const key = `${i}::${field}`;
      // Whatever it was before this session's apply; failing that, what the extractor
      // originally wrote. Never left stuck on the judge's value with no way back.
      const previous = review.undo.has(key)
        ? review.undo.get(key)
        : (review.modelRecords[i] || {})[field] ?? null;
      review.records[i][field] = previous;
      review.undo.delete(key);
      review.dirty = true;
      paintRecords();
    }));
    card.querySelectorAll('[data-find]').forEach(btn => btn.addEventListener('click', () => {
      // back through Number() where it is numeric: a dataset value is always a string, and the
      // decimal-tolerant forms of "42.7" are only generated for actual numbers
      const raw = btn.dataset.find;
      cycleField(i, btn.dataset.field, raw !== '' && !Number.isNaN(Number(raw)) ? Number(raw) : raw);
    }));
    card.querySelectorAll('[data-flag]').forEach(btn => btn.addEventListener('click', () => {
      const note = review.notes[i] || (review.notes[i] = {});
      note.flag = note.flag === btn.dataset.flag ? null : btn.dataset.flag;
      review.dirty = true;
      paintRecords();
    }));
    const note = card.querySelector('[data-note]');
    if (note) note.addEventListener('change', () => {
      review.notes[i] = { ...(review.notes[i] || {}), note: note.value || null };
      review.dirty = true;
      const save = document.getElementById('save-review');
      if (save) save.disabled = false;
    });
  });
}

async function saveReview() {
  const status = document.getElementById('save-status');
  status.textContent = 'Saving…';
  try {
    const saved = await put(`/api/papers/${review.paperId}/extraction`,
                            { records: review.records, notes: review.notes, version: review.version });
    review.dirty = false;
    review.version = saved.version;
    review.modelRecords = saved.model_records;   // what the model said, pinned on first edit
    status.textContent = 'Saved.';
    paintRecords();
  } catch (e) { status.textContent = 'Error: ' + e.message; }
}

async function loadReview(paperId, withJudgment) {
  if (!paperId) return;
  const wants = [get('/api/papers/' + paperId), get(`/api/papers/${paperId}/extraction`), get('/api/schema')];
  if (withJudgment) wants.push(get(`/api/papers/${paperId}/judgment`));
  const [paper, extraction, schema, judgment] = await Promise.all(wants);
  Object.assign(review, {
    paperId,
    chunks: paper.chunks,
    sourceTracking: paper.source_tracking,
    schema: schema.fields,
    records: extraction.records,
    version: extraction.version,
    modelRecords: extraction.model_records || extraction.records,
    notes: extraction.notes || {},
    verdicts: judgment ? new Map(judgment.verdicts.map(v => [v.record_index, v])) : null,
    selected: null, key: null, marks: [], markIndex: -1,
    editing: new Set(), undo: new Map(), dirty: false,
  });
  paintText(null);
  paintRecords();
}

function reviewPanelHTML(title) {
  return `<div class="panel">
    <h2>${title}</h2>
    <div class="row" style="margin-bottom:10px">
      <label style="margin:0">Paper</label>
      <select id="review-pick"></select>
      <span class="grow"></span>
      <span class="muted" id="match-counter"></span>
      <button id="delete-run">Delete this run</button>
      <button class="primary" id="save-review" disabled>Save corrections</button>
      <span class="muted" id="save-status"></span>
    </div>
    <p class="lede">Click a record to shade the chunks it cites; click a field to find its value
      in the text, again for the next match. Corrections save beside the model's original.</p>
    <div class="split">
      <div id="text-pane"><p class="muted">Pick a paper above.</p></div>
      <div id="rec-pane"></div>
    </div>
  </div>`;
}

function wireReviewPicker(papers, withJudgment) {
  const pick = document.getElementById('review-pick');
  pick.innerHTML = papers.map(p => `<option value="${p.id}">${esc(p.filename)}</option>`).join('')
    || `<option value="">(nothing ${withJudgment ? 'judged' : 'extracted'} yet)</option>`;
  pick.addEventListener('change', () => loadReview(pick.value, withJudgment));
  document.getElementById('save-review').addEventListener('click', saveReview);

  const stage = withJudgment ? 'judgment' : 'extraction';
  const deleteBtn = document.getElementById('delete-run');
  deleteBtn.disabled = !papers.length;
  deleteBtn.addEventListener('click', async () => {
    const id = pick.value;
    if (!id) return;
    const name = papers.find(p => p.id === id)?.filename || id;
    const extra = withJudgment
      ? '\n\nThe extracted records stay; only the verdicts go.'
      : '\n\nThis also deletes its judgment, and any corrections and notes you saved.';
    if (!confirm(`Delete the ${stage} for "${name}"?${extra}\n\nThis cannot be undone. `
                 + `You can re-run it, at the usual cost.`)) return;
    deleteBtn.disabled = true;
    try {
      await del(`/api/papers/${id}/${stage}`);
      router();
    } catch (e) {
      deleteBtn.disabled = false;
      alert('Could not delete: ' + e.message);
    }
  });

  if (papers.length) return loadReview(papers[0].id, withJudgment);
}

// ---------- Parse page ----------

function papersTableHTML(papers) {
  const spent = papers.reduce((n, p) => n + ((p.spend || {}).cost_usd || 0), 0);
  const totalTokens = papers.reduce((n, p) => n + ((p.spend || {}).tokens || 0), 0);
  return `<table>
    <thead><tr><th>File</th><th>Chunks</th><th>Source</th><th>Records</th><th>Judged</th>
      <th style="text-align:right">Cost</th><th></th></tr></thead>
    <tbody>${papers.map(p => {
      const spend = p.spend || {};
      return `<tr data-id="${p.id}">
        <td>${esc(p.filename)}</td>
        <td class="muted">${p.n_chunks}</td>
        <td><span class="tag ${p.source_tracking ? 'yes' : 'no'}">${p.source_tracking ? 'on' : 'off'}</span></td>
        <td>${p.n_records === null || p.n_records === undefined
              ? '<span class="tag no">not extracted</span>'
              : p.n_records === 0
                ? '<span class="tag warn" title="the model found nothing matching your prompt and schema">0 &mdash; nothing found</span>'
                : `<span class="tag yes">${p.n_records}</span>`}</td>
        <td><span class="tag ${p.judged ? 'yes' : 'no'}">${p.judged ? 'yes' : 'no'}</span></td>
        ${spendCell(spend.cost_usd, spend.tokens)}
        <td class="nowrap">
          <button class="view-btn">View</button>
          <button class="del-btn" data-name="${esc(p.filename)}"
            data-has="${[p.extracted && 'extraction', p.judged && 'judgment'].filter(Boolean).join(' and ')}">Delete</button>
        </td>
      </tr>`;
    }).join('') || '<tr><td colspan="7" class="muted">No papers yet</td></tr>'}</tbody>
    ${(spent || totalTokens) ? `<tfoot><tr><td colspan="5" class="muted">total</td>
      ${spendCell(spent, totalTokens)}<td></td></tr></tfoot>` : ''}
  </table>`;
}

async function renderParse(gen) {
  const [papers, settings, timings] = await Promise.all([
    get('/api/papers'), get('/api/settings'), get('/api/timings')]);
  if (stale(gen)) return;
  state.timings = timings;

  view.innerHTML = `
    <section>
      <div class="panel">
        <h2>Add papers</h2>
        <p class="lede">Parsed locally into text and table chunks. ${esc(etaText('parse'))} per
          paper; scanned PDFs take longer. You can leave this tab while it runs.</p>
        <div class="pickers">
          <label class="pickbtn">Choose PDF files
            <input type="file" id="pdf-files" accept="application/pdf" multiple hidden></label>
          <label class="pickbtn">Choose a whole folder
            <input type="file" id="pdf-folder" webkitdirectory multiple hidden></label>
          <button id="clear-pick" hidden>Clear</button>
        </div>
        <div id="picked" class="picked muted">No files chosen yet.</div>
        <label style="margin-top:10px"><input type="checkbox" id="src-track" ${settings.source_tracking_default ? 'checked' : ''}>
          Source tracking &mdash; tag every chunk with an id so records can cite where a value came from</label>
        <div class="row" style="margin-top:10px">
          <button class="primary" id="upload-btn" disabled>Parse</button>
          <span class="muted" id="upload-hint"></span>
        </div>
        <div id="run-progress"></div>
      </div>
      <div class="panel">
        <h2>Papers <span class="muted" style="font-weight:400" id="paper-count">${papers.length}</span></h2>
        <div id="papers-table">${papersTableHTML(papers)}</div>
      </div>
      <div class="panel" id="preview-panel" style="display:none">
        <h2 id="preview-title"></h2>
        <div id="preview-text" class="chunks" style="max-height:60vh;overflow-y:auto"></div>
      </div>
    </section>`;

  paintRun();

  const refreshPapers = async () => {
    const fresh = await get('/api/papers');
    const table = document.getElementById('papers-table');
    if (!table) return;
    table.innerHTML = papersTableHTML(fresh);
    wireViewButtons();
    wireDeleteButtons(refreshPapers);
    const count = document.getElementById('paper-count');
    if (count) count.textContent = fresh.length;
  };
  wireViewButtons();
  wireDeleteButtons(refreshPapers);

  let picked = [];
  const pickedBox = document.getElementById('picked');
  const uploadBtn = document.getElementById('upload-btn');
  const clearBtn = document.getElementById('clear-pick');

  // What you chose, spelled out. The browser's own "12 files" label sits inside a control we
  // hide, and "no files chosen" next to a Parse button was the whole of the previous feedback.
  function showPicked() {
    uploadBtn.disabled = !picked.length || runIsActive();
    clearBtn.hidden = !picked.length;
    if (!picked.length) {
      pickedBox.className = 'picked muted';
      pickedBox.textContent = 'No files chosen yet.';
      uploadBtn.textContent = 'Parse';
      return;
    }
    const mb = picked.reduce((n, f) => n + f.size, 0) / 1e6;
    const total = (() => {
      const seconds = picked.reduce((n, f) => n + (parseEta(f) || 0), 0);
      if (!seconds) return 'no time estimate yet \u2014 the first parse sets one';
      return `about <b>${humanSeconds(seconds)}</b> in total`;
    })();
    pickedBox.className = 'picked';
    pickedBox.innerHTML = `<b>${picked.length} PDF${picked.length === 1 ? '' : 's'} chosen</b>
      <span class="muted">${mb.toFixed(1)} MB · ${total}</span>
      <div class="filelist">${picked.map(f => `<div>${esc(f.webkitRelativePath || f.name)}</div>`).join('')}</div>`;
    uploadBtn.textContent = `Parse ${picked.length} PDF${picked.length === 1 ? '' : 's'}`;
  }

  const addFiles = (fileList) => {
    const pdfs = [...fileList].filter(f => f.name.toLowerCase().endsWith('.pdf'));
    const skipped = fileList.length - pdfs.length;
    const seen = new Set(picked.map(f => (f.webkitRelativePath || f.name) + f.size));
    picked = picked.concat(pdfs.filter(f => !seen.has((f.webkitRelativePath || f.name) + f.size)));
    document.getElementById('upload-hint').textContent =
      skipped ? `${skipped} non-PDF file${skipped === 1 ? '' : 's'} in that folder ignored.` : '';
    showPicked();
  };

  document.getElementById('pdf-files').addEventListener('change', e => addFiles(e.target.files));
  document.getElementById('pdf-folder').addEventListener('change', e => addFiles(e.target.files));
  clearBtn.addEventListener('click', () => { picked = []; showPicked(); });
  showPicked();

  uploadBtn.addEventListener('click', async () => {
    if (runIsActive()) return;
    const srcTrack = document.getElementById('src-track').checked;
    const items = picked.map(f => ({ label: f.webkitRelativePath || f.name, file: f, eta: parseEta(f) }));
    uploadBtn.disabled = true;
    await runJob('Parsing', items, async (item) => {
      const fd = new FormData();
      fd.append('files', item.file);
      const [r] = await post('/api/papers?source_tracking=' + srcTrack, fd);
      if (r.error) throw new Error(r.error);
      return `${r.n_chunks} chunks in ${humanSeconds(r.seconds)}`;
    });
    picked = [];
    showPicked();
    await refreshPapers();
  });
}

// Deleting is the one irreversible thing in the app, so the confirm names what goes with it:
// an extraction carries the reviewer's corrections and notes, and those cannot be re-derived
// by re-running anything.
function wireDeleteButtons(onDone) {
  document.querySelectorAll('.del-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    const row = e.target.closest('tr');
    const id = row.dataset.id;
    const has = btn.dataset.has;
    const name = btn.dataset.name || id;
    const extra = has
      ? `\n\nThis also deletes its ${has}, including any corrections and notes you saved.`
      : '';
    if (!confirm(`Delete "${name}"?${extra}\n\nThis cannot be undone.`)) return;
    btn.disabled = true;
    try {
      await del('/api/papers/' + id);
      onDone();
    } catch (err) {
      btn.disabled = false;
      alert('Could not delete: ' + err.message);
    }
  }));
}

function wireViewButtons() {
  document.querySelectorAll('.view-btn').forEach(btn => btn.addEventListener('click', async (e) => {
    const id = e.target.closest('tr').dataset.id;
    const paper = await get('/api/papers/' + id);
    const panel = document.getElementById('preview-panel');
    if (!panel) return;
    panel.style.display = '';
    document.getElementById('preview-title').textContent = paper.filename;
    document.getElementById('preview-text').innerHTML = paper.chunks.map(c =>
      `<div class="chunk" data-id="${c.id}">` +
      (paper.source_tracking ? `<span class="cid">${c.id.slice(0, 8)}</span>` : '') +
      c.html + '</div>').join('');
    panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }));
}

// ---------- Extract / Judge pages (same shape) ----------

function stageChecklistHTML(papers, doneKey, emptyMsg) {
  return papers.map(p =>
    `<label><input type="checkbox" value="${p.id}" ${p[doneKey] ? '' : 'checked'}>
      ${esc(p.filename)} <span class="muted">${p.n_chunks} chunks</span>
      ${p[doneKey] ? `<span class="tag yes">already done</span>` : ''}</label>`).join('') || emptyMsg;
}

async function renderExtract(gen) {
  const [papers, timings] = await Promise.all([get('/api/papers'), get('/api/timings')]);
  if (stale(gen)) return;
  state.timings = timings;

  view.innerHTML = `
    <section>
      <div class="panel">
        <h2>Extract</h2>
        <p class="lede">One call per paper, using the schema and prompt from
          <a href="#/settings">Settings</a>. ${esc(etaText('extract', 30))} for a typical paper.</p>
        <div class="checklist" id="checklist">${stageChecklistHTML(papers, 'extracted',
          '<span class="muted">No parsed papers yet &mdash; start in <a href="#/parse">Parse</a>.</span>')}</div>
        <div class="muted" id="selection-summary" style="margin-top:8px"></div>
        <div class="row" style="margin-top:10px">
          <button class="primary" id="run-btn">Run extraction on selected</button>
          <span class="muted" id="select-hint"></span>
        </div>
        <div id="run-progress"></div>
      </div>
      ${reviewPanelHTML('Review')}
    </section>`;

  paintRun();
  wireStageRun(papers, 'extract', 'Extracting',
    (r) => `${r.n_records} records · ${humanSeconds(r.seconds)}${costOf(r)}`);
  await wireReviewPicker(papers.filter(p => p.extracted), false);
}

async function renderJudge(gen) {
  const [papers, timings] = await Promise.all([get('/api/papers'), get('/api/timings')]);
  if (stale(gen)) return;
  state.timings = timings;
  const extracted = papers.filter(p => p.extracted);

  view.innerHTML = `
    <section>
      <div class="panel">
        <h2>Judge</h2>
        <p class="lede">A second model re-reads each paper and checks every record against it.
          ${esc(etaText('judge', 18))} for a typical paper.</p>
        <div class="checklist" id="checklist">${stageChecklistHTML(extracted, 'judged',
          '<span class="muted">Nothing extracted yet &mdash; run <a href="#/extract">Extract</a> first.</span>')}</div>
        <div class="muted" id="selection-summary" style="margin-top:8px"></div>
        <div class="row" style="margin-top:10px">
          <button class="primary" id="run-btn">Run judge on selected</button>
          <span class="muted" id="select-hint"></span>
        </div>
        <div id="run-progress"></div>
      </div>
      ${reviewPanelHTML('Review')}
    </section>`;

  paintRun();
  wireStageRun(extracted, 'judge', 'Judging',
    (r) => `${r.n_verdicts} verdicts · ${humanSeconds(r.seconds)}${costOf(r)}`);
  await wireReviewPicker(papers.filter(p => p.judged), true);
}

function etaFor(endpoint, paper) {
  const t = state.timings[endpoint];
  if (!t) return null;
  const size = endpoint === 'extract' ? paper?.n_chunks : null;
  return (t.per_unit && size) ? t.per_unit * size : t.seconds;
}

function wireStageRun(papers, endpoint, stageLabel, describe) {
  const btn = document.getElementById('run-btn');
  const checklist = document.getElementById('checklist');
  const byId = new Map(papers.map(p => [p.id, p]));

  // What the batch will cost you, before you commit to it -- a per-paper figure leaves the
  // reader multiplying in their head, and the total is the number that decides whether this
  // is a coffee break or an overnight run.
  const summary = document.getElementById('selection-summary');
  const updateSummary = () => {
    const ids = [...checklist.querySelectorAll('input:checked')].map(i => i.value);
    if (!summary) return;
    if (!ids.length) { summary.textContent = 'Nothing selected.'; btn.disabled = true; return; }
    btn.disabled = runIsActive();
    const etas = ids.map(id => etaFor(endpoint, byId.get(id)));
    const total = etas.every(e => e !== null) ? etas.reduce((a, b) => a + b, 0) : null;
    summary.innerHTML = `<b>${ids.length} paper${ids.length === 1 ? '' : 's'} selected</b>` +
      (total ? ` · about <b>${humanSeconds(total)}</b> in total` : ' · no time estimate yet');
  };
  checklist.addEventListener('change', updateSummary);
  updateSummary();

  if (runIsActive()) { btn.disabled = true; btn.textContent = 'a run is already in progress'; }
  btn.addEventListener('click', async () => {
    if (runIsActive()) return;
    const ids = [...checklist.querySelectorAll('input:checked')].map(i => i.value);
    const hint = document.getElementById('select-hint');
    if (!ids.length) { hint.textContent = 'Tick at least one paper first.'; return; }
    hint.textContent = '';
    btn.disabled = true;
    const startedOn = location.hash;
    const items = ids.map(id => ({
      label: byId.get(id)?.filename || id, id, eta: etaFor(endpoint, byId.get(id)),
    }));
    await runJob(stageLabel, items, async (item, slot) => {
      const [r] = await post('/api/' + endpoint, { paper_ids: [item.id] });
      if (r.error) throw new Error(r.error);
      if (r.usage && r.usage.cost_usd) slot.cost = r.usage.cost_usd;
      return describe(r);
    });
    btn.disabled = false;
    // Refresh statuses and the review picker -- but only if they are still on the page that
    // started the run. Re-rendering whatever tab they wandered to would throw away unsaved
    // edits sitting in a Settings textarea, which is a worse bug than a stale checklist.
    if (location.hash === startedOn) router();
  });
}

// ---------- Report ----------
//
// Inline SVG rather than a charting library: this tool is meant to run on a laptop with no
// network, and every CDN script it pulled would be one more thing to be offline.

const trunc = (s, n) => String(s).length > n ? String(s).slice(0, n - 1) + '…' : String(s);
const num = (x) => Number.isInteger(x) ? String(x) : x.toFixed(x < 10 ? 2 : 1);

function hbars(items, { unit = '', max = null } = {}) {
  if (!items.length) return '<p class="muted">nothing to show yet</p>';
  const top = max ?? Math.max(...items.map(i => i.value), 1);
  const rowH = 22, labelW = 168, barW = 300, w = labelW + barW + 92;
  const gridAt = max === 100 ? [25, 50, 75, 100] : [];
  const grid = gridAt.map(g => {
    const x = labelW + barW * g / 100;
    return `<line class="grid" x1="${x}" y1="0" x2="${x}" y2="${items.length * rowH}"/>`;
  }).join('');
  const rows = items.map((it, i) => {
    const y = i * rowH + 4;
    const len = it.value > 0 ? Math.max(2, barW * it.value / top) : 0;
    return `<text x="${labelW - 8}" y="${y + 11}" text-anchor="end">${esc(trunc(it.label, 26))}
        <title>${esc(it.label)}</title></text>
      <rect class="track" x="${labelW}" y="${y + 2}" width="${barW}" height="12" rx="3"/>
      <rect class="fill ${it.tone || ''}" x="${labelW}" y="${y + 2}" width="${len}" height="12" rx="3">
        <title>${esc(it.label)}: ${it.value}${unit}${it.hint ? ' \u2014 ' + esc(it.hint) : ''}</title></rect>
      <text class="val" x="${labelW + barW + 8}" y="${y + 11}">${esc(it.text ?? (it.value + unit))}</text>`;
  }).join('');
  return `<svg viewBox="0 0 ${w} ${items.length * rowH + 8}">${grid}${rows}</svg>`;
}

function histogram(values, { bins = 24, unit = '' } = {}) {
  if (!values.length) return '<p class="muted">no numeric values recorded for this field</p>';
  const min = Math.min(...values), max = Math.max(...values);
  if (min === max) return `<p class="muted">every one of the ${values.length} values is ${num(min)}${unit}</p>`;
  const counts = new Array(bins).fill(0);
  for (const v of values) counts[Math.min(bins - 1, Math.floor((v - min) / (max - min) * bins))]++;
  const top = Math.max(...counts), w = 560, h = 150, padB = 22, barW = w / bins;
  const bars = counts.map((c, i) => {
    const bh = (h - padB) * c / top;
    const lo = min + (max - min) * i / bins, hi = min + (max - min) * (i + 1) / bins;
    return `<rect class="fill" x="${i * barW + 1}" y="${h - padB - bh}" width="${barW - 2}"
      height="${bh}" rx="2"><title>${num(lo)}–${num(hi)}${unit}: ${c} records</title></rect>`;
  }).join('');
  return `<svg viewBox="0 0 ${w} ${h}">${bars}
    <line class="axis" x1="0" y1="${h - padB}" x2="${w}" y2="${h - padB}"/>
    <text x="0" y="${h - 6}">${num(min)}${unit}</text>
    <text class="val" x="${w / 2}" y="${h - 6}" text-anchor="middle">${values.length} values</text>
    <text x="${w}" y="${h - 6}" text-anchor="end">${num(max)}${unit}</text></svg>`;
}

function splitBar(parts) {
  const total = parts.reduce((n, p) => n + p.value, 0);
  if (!total) return '<p class="muted">nothing judged yet</p>';
  let x = 0;
  const segs = parts.filter(p => p.value).map(p => {
    const w = 560 * p.value / total;
    const seg = `<rect x="${x}" y="0" width="${w}" height="24" fill="${p.color}" rx="2">
      <title>${esc(p.label)}: ${p.value} (${(100 * p.value / total).toFixed(1)}%)</title></rect>`;
    x += w;
    return seg;
  }).join('');
  const legend = parts.filter(p => p.value).map(p =>
    `<span class="muted"><span style="display:inline-block;width:9px;height:9px;border-radius:2px;
      background:${p.color}"></span> ${esc(p.label)} ${p.value}
      (${(100 * p.value / total).toFixed(0)}%)</span>`).join(' &nbsp; ');
  return `<svg viewBox="0 0 560 24" style="max-height:24px">${segs}</svg>
    <div class="row" style="margin-top:8px;gap:12px">${legend}</div>`;
}

function chart(title, sub, body) {
  return `<div class="chart"><h3>${title}</h3><div class="sub">${sub}</div>${body}</div>`;
}

async function renderReport(gen) {
  const data = await get('/api/report');
  if (stale(gen)) return;
  const t = data.totals;
  const withRecords = data.fields.filter(f => f.total > 0);
  const verdictTotal = Object.values(t.verdicts).reduce((a, b) => a + b, 0);
  const correctShare = verdictTotal ? (t.verdicts.correct || 0) / verdictTotal : null;
  const explorable = withRecords.filter(f => f.numbers.length || f.top.length);
  const intervened = withRecords.filter(f => f.bad || f.corrections).sort((a, b) => b.bad - a.bad);
  const worked = data.papers.filter(p => p.records || p.judged);
  const spend = t.spend || { cost_usd: 0, calls: 0, prompt_tokens: 0, completion_tokens: 0 };
  const spendTokens = spend.prompt_tokens + spend.completion_tokens;

  if (!t.records) {
    view.innerHTML = `<section><div class="panel empty">
      <h2>Nothing to report yet</h2>
      <p class="muted">Parse some papers and run an extraction; this page then describes the
        corpus you have built — completeness by field, what the judge changed, and the
        distribution of any field you pick.</p>
      <a href="#/parse"><button class="primary">Go to Parse</button></a>
    </div></section>`;
    paintRun();
    return;
  }

  // Completeness is the one number where low is bad, so it is coloured rather than left neutral:
  // a field that is 8% filled is a finding, not a bar.
  const completeness = [...withRecords].sort((a, b) => b.completeness - a.completeness).map(f => ({
    label: f.name,
    value: f.completeness,
    text: `${f.completeness}%`,
    tone: f.completeness >= 80 ? 'good' : f.completeness >= 40 ? 'mid' : 'weak',
    hint: `${f.filled} of ${f.total} records`,
  }));

  view.innerHTML = `
    <section>
      <div class="reporthead">
        <div>
          <h2 style="margin:0">Corpus report</h2>
          <p class="muted" style="margin:2px 0 0">${t.records.toLocaleString()} records from
            ${t.papers_extracted} extracted paper${t.papers_extracted === 1 ? '' : 's'},
            ${t.papers_judged} audited by the judge.</p>
        </div>
        <span class="grow"></span>
        <a href="/api/export.csv" download><button>Export CSV</button></a>
        <a href="/api/export.json" download><button>Export JSON</button></a>
      </div>

      <div class="cards">
        ${statCard(t.papers_parsed, 'papers parsed',
          `${t.papers_extracted} extracted · ${t.papers_judged} judged` +
          (t.papers_without_records ? ` · ${t.papers_without_records} found nothing` : ''))}
        ${statCard(t.records.toLocaleString(), 'records extracted',
          worked.length ? `median ${median(t.records_per_paper)} per paper` : '')}
        ${statCard(correctShare === null ? '—' : `${Math.round(100 * correctShare)}%`, 'judged correct',
          verdictTotal ? `${t.verdicts.incorrect || 0} flagged of ${verdictTotal}` : 'nothing judged yet',
          correctShare !== null && correctShare < 0.8 ? 'warn' : '')}
        ${statCard(t.records_edited, 'corrected by you',
          t.flags.ok || t.flags.bad ? `${t.flags.ok || 0} marked right · ${t.flags.bad || 0} marked wrong` : 'no manual review yet')}
        ${statCard(
          spend.cost_usd ? '$' + spend.cost_usd.toFixed(2) : (spendTokens ? tokens(spendTokens) : '—'),
          spend.cost_usd ? 'spent on models' : (spendTokens ? 'tokens used' : 'model usage'),
          spend.calls
            ? `${spend.calls} calls` + (spend.cost_usd ? '' : ' · this model has no public price')
            : 'no calls recorded yet')}
      </div>

      <div class="charts">
        ${chart('Completeness by field',
          'Share of records carrying a value for each field.',
          hbars(completeness, { max: 100 }))}

        ${chart('Judge verdicts',
          verdictTotal
            ? `${verdictTotal} record${verdictTotal === 1 ? '' : 's'} audited` +
              (t.records_dropped_by_judge ? ` · ${t.records_dropped_by_judge} it would drop outright` : '')
            : 'Run the judge to fill this in.',
          splitBar([
            { label: 'correct', value: t.verdicts.correct || 0, color: 'var(--ok)' },
            { label: 'incorrect', value: t.verdicts.incorrect || 0, color: 'var(--no)' },
            { label: 'unparsed', value: t.verdicts.unparsed || 0, color: 'var(--dim)' },
          ]))}

        ${chart('Fields the judge flagged',
          'Flagged by the judge, and how many it could propose a value for.',
          intervened.length
            ? hbars(intervened.map(f => ({
                label: f.name, value: f.bad, tone: 'weak',
                text: `${f.bad} flagged${f.corrections ? `, ${f.corrections} fixed` : ''}` })))
            : '<p class="muted">The judge changed nothing — either the extraction is clean or it has not run yet.</p>')}

        ${chart('Records per paper',
          'Papers yielding none are usually out of scope or mis-parsed.',
          t.records_per_paper.length > 8
            ? histogram(t.records_per_paper, { bins: 16 })
            : hbars(worked.map(p => ({ label: p.filename, value: p.records,
                tone: p.records ? 'good' : 'weak' }))))}
      </div>

      <div class="panel">
        <div class="row" style="margin-bottom:10px">
          <h3 style="margin:0">Explore a field</h3>
          <select id="field-pick">${explorable.map(f =>
            `<option value="${esc(f.name)}">${esc(f.name)}</option>`).join('')}</select>
          <span class="muted">numeric fields show a distribution; text fields their commonest values</span>
        </div>
        <div id="field-detail"></div>
      </div>

      <div class="panel">
        <h3 style="margin:0 0 10px">Per paper</h3>
        <table><thead><tr><th>Paper</th><th style="width:76px">Chunks</th>
          <th style="width:148px">Records</th><th style="width:116px">Judge flagged</th>
          <th style="width:104px">You reviewed</th>
          <th style="width:92px;text-align:right">Cost</th></tr></thead>
          <tbody>${data.papers.map(p => {
            const most = Math.max(...data.papers.map(x => x.records), 1);
            return `<tr>
              <td>${esc(p.filename)}</td>
              <td class="muted">${p.chunks}</td>
              <td><span class="minibar"><i style="width:${100 * p.records / most}%"></i></span>
                  <span class="val">${p.records}</span></td>
              <td>${p.judged
                ? (p.incorrect ? `<span class="tag no">${p.incorrect}</span>` : '<span class="tag yes">none</span>')
                : '<span class="muted">not judged</span>'}</td>
              <td>${p.reviewed ? `<span class="tag yes">${p.reviewed}</span>` : '<span class="muted">—</span>'}</td>
              ${spendCell(p.cost_usd, p.tokens)}
            </tr>`;
          }).join('')}</tbody>
          ${(spend.cost_usd || spendTokens) ? `<tfoot><tr><td colspan="5" class="muted">total</td>
            ${spendCell(spend.cost_usd, spendTokens)}</tr></tfoot>` : ''}</table>
      </div>
    </section>`;

  paintRun();

  const pick = document.getElementById('field-pick');
  const paintField = () => {
    const f = explorable.find(x => x.name === pick.value);
    const host = document.getElementById('field-detail');
    if (!f) { host.innerHTML = '<p class="muted">No fields carry values yet.</p>'; return; }
    host.innerHTML = f.numbers.length
      ? chart(`${esc(f.name)}`,
          `${f.filled} of ${f.total} records carry a value (${f.completeness}%).`,
          histogram(f.numbers))
      : chart(`${esc(f.name)}`,
          `${f.top.length >= 25 ? 'The 25 commonest of the' : 'All'} distinct values across ${f.filled} records.`,
          hbars(f.top.map(([label, value]) => ({ label, value }))));
  };
  if (pick) { pick.addEventListener('change', paintField); paintField(); }
}

function median(xs) {
  if (!xs.length) return 0;
  const s = [...xs].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2);
}

function statCard(n, label, sub, tone = '') {
  return `<div class="stat ${tone}">
    <div class="n">${n}</div>
    <div class="l">${label}</div>
    ${sub ? `<div class="s">${esc(sub)}</div>` : ''}
  </div>`;
}


// ---------- Settings ----------

async function renderSettings(gen) {
  const [settings, schema, prompts, fewShot, envKeys, papers] = await Promise.all([
    get('/api/settings'), get('/api/schema'), get('/api/prompts'), get('/api/few-shot'),
    get('/api/env-keys'), get('/api/papers'),
  ]);
  if (stale(gen)) return;

  view.innerHTML = `
    <section>
      <p class="lede">The model, the schema, the prompt and the rubric are all that decide what
        gets extracted. Change them and the same pipeline works on any literature.</p>

      <div class="panel">
        <h2>Model</h2>
        <div class="field">
          <label>Model (litellm format)</label>
          <input id="model-input" value="${esc(settings.model)}" style="width:100%">
          <p class="muted" style="margin-top:6px">
            <code>gpt-4o-mini</code> &middot; <code>anthropic/claude-sonnet-4-5</code> &middot;
            <code>ollama/llama3</code> &middot; <code>azure/your-deployment-name</code>.
            <a href="https://docs.litellm.ai/docs/providers" target="_blank">Full list</a>.</p>
        </div>
        <div class="row">
          <button class="primary" id="save-settings">Save model</button>
          <button id="test-model">Test connection</button>
          <span class="muted" id="settings-status"></span>
        </div>
        <h3 style="margin-top:20px">Keys</h3>
        <p class="lede" style="margin-bottom:10px">Stored in this project's local
          <code>.env</code>. Azure needs all three rows; other providers need one.</p>
        <table class="keys"><tbody id="key-rows"></tbody></table>
        <div class="row" style="margin-top:10px">
          <input id="new-key-name" placeholder="ANOTHER_VARIABLE_NAME" style="width:230px">
          <input id="new-key-value" type="password" placeholder="value" style="flex:1">
          <button class="primary" id="add-key">Add variable</button>
          <span class="muted" id="key-status"></span>
        </div>
      </div>

      <div class="panel">
        <h2>Schema</h2>
        <p class="lede">The fields one record carries. Descriptions are read by the model.</p>
        <table class="schema-table"><thead><tr>
          <th style="width:24%">Field name</th><th style="width:14%">Type</th><th>Description (the model reads this)</th><th></th>
        </tr></thead><tbody id="schema-rows"></tbody></table>
        <div class="row" style="margin-top:10px">
          <button id="add-field">+ Add field</button>
          <button class="primary" id="save-schema">Save schema</button>
          <span class="muted" id="schema-status"></span>
        </div>
        <p class="muted">Changing this does not re-run existing extractions.</p>
      </div>

      <div class="panel">
        <h2>Extraction prompt</h2>
        <div class="hint" style="margin-bottom:10px">
          <b>Draft one for your domain</b>
          <p>Name the field and the model drafts a prompt around your schema, grounded in a paper
            you have already parsed. It lands below for you to edit.</p>
          <div class="row">
            <input id="gen-domain" placeholder="e.g. metal salt catalysed PET glycolysis" style="flex:1;min-width:240px">
            <select id="gen-paper"><option value="">(no example paper)</option>
              ${papers.map(p => `<option value="${p.id}">${esc(p.filename)}</option>`).join('')}</select>
            <button id="gen-extract">Draft prompt</button>
            <span class="muted" id="gen-extract-status"></span>
          </div>
        </div>
        <textarea id="extract-prompt" rows="12">${esc(prompts.extract)}</textarea>
        <div class="row" style="margin-top:10px"><button class="primary" id="save-extract-prompt">Save prompt</button>
          <span class="muted" id="extract-prompt-status"></span></div>
      </div>

      <div class="panel">
        <h2>Judge rubric</h2>
        <div class="hint" style="margin-bottom:10px">
          <b>Draft one for your domain</b>
          <p>What makes a record right or wrong in this field.</p>
          <div class="row">
            <input id="gen-domain-judge" placeholder="e.g. metal salt catalysed PET glycolysis" style="flex:1;min-width:240px">
            <button id="gen-judge">Draft rubric</button>
            <span class="muted" id="gen-judge-status"></span>
          </div>
        </div>
        <textarea id="judge-prompt" rows="12">${esc(prompts.judge)}</textarea>
        <div class="row" style="margin-top:10px"><button class="primary" id="save-judge-prompt">Save rubric</button>
          <span class="muted" id="judge-prompt-status"></span></div>
      </div>

      <div class="panel">
        <h2>Worked examples <span class="muted" style="font-weight:400">optional</span></h2>
        <p class="lede">A paper's text paired with the records it should produce, shown to the
          model before each extraction. One good example teaches more than a long prompt &mdash;
          but its text is re-sent with every paper, so two or three is the practical ceiling.</p>

        <div class="hint">
          <b>Add an example</b>
          <div class="row" style="margin-top:8px">
            <select id="fs-source">${papers.filter(p => p.extracted).map(p =>
              `<option value="${p.id}">${esc(p.filename)}</option>`).join('')
              || '<option value="">(no extracted papers yet)</option>'}</select>
            <button id="fs-add">Add from this paper</button>
            <button id="fs-add-blank">Add an empty one</button>
            <span class="muted" id="fs-add-status"></span>
          </div>
          <p>Copies the paper's text and its current, corrected records &mdash; so correct it in
            the Extract review first. Add as many as you like.</p>
        </div>

        <div class="row" style="margin:14px 0 8px">
          <span class="muted" id="fs-count"></span>
          <span class="grow"></span>
          <button class="primary" id="save-few-shot">Save all examples</button>
          <span class="muted" id="few-shot-status"></span>
        </div>
        <div id="fs-list"></div>

      <div class="panel">
        <h2>Defaults</h2>
        <label><input type="checkbox" id="src-default" ${settings.source_tracking_default ? 'checked' : ''}>
          Turn source tracking on for newly uploaded papers</label>
        <div class="row" style="margin-top:10px"><button class="primary" id="save-defaults">Save defaults</button>
          <span class="muted" id="defaults-status"></span></div>
      </div>
    </section>`;

  paintRun();

  const say = async (statusId, fn) => {
    const status = document.getElementById(statusId);
    status.textContent = 'Working…';
    try { const msg = await fn(); status.textContent = msg || 'Saved.'; }
    catch (e) { status.textContent = 'Error: ' + e.message; }
  };
  const on = (id, statusId, fn) => document.getElementById(id).addEventListener('click', () => say(statusId, fn));

  // --- model + keys
  on('save-settings', 'settings-status', async () => {
    await put('/api/settings', { model: document.getElementById('model-input').value.trim() });
    document.getElementById('model-badge').textContent = 'model: ' + document.getElementById('model-input').value.trim();
  });
  on('test-model', 'settings-status', async () => {
    const r = await post('/api/test-model', {});
    if (!r.ok) throw new Error(r.error);
    return `${r.model} replied in ${r.seconds}s — working.`;
  });

  // One row per variable, each editable where it sits. The stored value is fetched only when
  // Edit is pressed on that row, so no secret sits in the page waiting for a screen-share.
  const keyRows = document.getElementById('key-rows');
  const keyState = { ...envKeys };
  let editingKey = null;

  function paintKeys() {
    keyRows.innerHTML = Object.entries(keyState).map(([name, info]) => {
      if (editingKey === name) {
        return `<tr data-key="${esc(name)}">
          <td><code>${esc(name)}</code></td>
          <td colspan="2"><input class="key-input" type="text" value="${esc(info.draft ?? '')}"
             placeholder="paste the value" style="width:100%"></td>
          <td class="nowrap">
            <button class="primary" data-save-key="${esc(name)}">Save</button>
            <button data-cancel-key="${esc(name)}">Cancel</button></td></tr>`;
      }
      return `<tr data-key="${esc(name)}">
        <td><code>${esc(name)}</code></td>
        <td><span class="tag ${info.set ? 'yes' : 'no'}">${info.set ? 'set' : 'not set'}</span></td>
        <td class="keyprev">${info.set ? esc(info.preview) : '<span class="muted">not set</span>'}</td>
        <td class="nowrap"><button data-edit-key="${esc(name)}">${info.set ? 'Edit' : 'Set'}</button></td></tr>`;
    }).join('');

    keyRows.querySelectorAll('[data-edit-key]').forEach(b => b.addEventListener('click', () =>
      say('key-status', async () => {
        const name = b.dataset.editKey;
        const r = await get('/api/api-key/' + encodeURIComponent(name));
        keyState[name] = { ...keyState[name], draft: r.value };
        editingKey = name;
        paintKeys();
        const box = keyRows.querySelector('.key-input');
        if (box) box.focus();
        return r.value ? 'Editing ' + name : name + ' is empty, paste a value.';
      })));

    keyRows.querySelectorAll('[data-cancel-key]').forEach(b => b.addEventListener('click', () => {
      delete keyState[b.dataset.cancelKey].draft;
      editingKey = null;
      paintKeys();
    }));

    keyRows.querySelectorAll('[data-save-key]').forEach(b => b.addEventListener('click', () =>
      say('key-status', async () => {
        const name = b.dataset.saveKey;
        const value = keyRows.querySelector('.key-input').value;
        if (!value) throw new Error('paste a value, or press Cancel');
        await put('/api/api-key', { name, value });
        editingKey = null;
        Object.assign(keyState, await get('/api/env-keys'));
        paintKeys();
        return name + ' saved.';
      })));
  }
  paintKeys();

  on('add-key', 'key-status', async () => {
    const name = document.getElementById('new-key-name').value.trim().toUpperCase();
    const value = document.getElementById('new-key-value').value;
    if (!name) throw new Error('name the variable first');
    if (!value) throw new Error('paste the value first');
    await put('/api/api-key', { name, value });
    document.getElementById('new-key-name').value = '';
    document.getElementById('new-key-value').value = '';
    Object.assign(keyState, await get('/api/env-keys'));
    paintKeys();
    return name + ' added.';
  });

  // --- schema table
  const rows = document.getElementById('schema-rows');
  const TYPES = ['string', 'number', 'integer', 'boolean'];
  const addRow = (f = { name: '', type: 'string', description: '' }) => rows.append(el(`
    <tr>
      <td><input class="f-name" value="${esc(f.name)}" placeholder="field_name"></td>
      <td><select class="f-type">${TYPES.map(t =>
        `<option ${f.type === t ? 'selected' : ''}>${t}</option>`).join('')}</select></td>
      <td><input class="f-desc" value="${esc(f.description || '')}" placeholder="what the model should put here"></td>
      <td><button class="f-del" title="remove">&times;</button></td>
    </tr>`));
  schema.fields.forEach(addRow);
  rows.addEventListener('click', e => { if (e.target.classList.contains('f-del')) e.target.closest('tr').remove(); });
  document.getElementById('add-field').addEventListener('click', () => addRow());
  on('save-schema', 'schema-status', () => put('/api/schema', {
    fields: [...rows.querySelectorAll('tr')].map(tr => ({
      name: tr.querySelector('.f-name').value.trim(),
      type: tr.querySelector('.f-type').value,
      description: tr.querySelector('.f-desc').value.trim(),
    })).filter(f => f.name),
  }).then(() => 'Saved.'));

  // --- prompts
  on('save-extract-prompt', 'extract-prompt-status', () =>
    put('/api/prompts', { extract: document.getElementById('extract-prompt').value }).then(() => 'Saved.'));
  on('save-judge-prompt', 'judge-prompt-status', () =>
    put('/api/prompts', { judge: document.getElementById('judge-prompt').value }).then(() => 'Saved.'));

  // --- prompt drafting
  const draft = (target, kind, domainId, statusId, paperId) => say(statusId, async () => {
    const domain = document.getElementById(domainId).value.trim();
    if (!domain) throw new Error('say what the corpus is about first');
    const paper_id = paperId ? document.getElementById(paperId).value || null : null;
    const r = await post('/api/generate-prompt', { kind, domain, paper_id });
    document.getElementById(target).value = r.prompt;
    return `Drafted by ${r.model} — read it, edit it, then Save.`;
  });
  document.getElementById('gen-extract').addEventListener('click', () =>
    draft('extract-prompt', 'extract', 'gen-domain', 'gen-extract-status', 'gen-paper'));
  document.getElementById('gen-judge').addEventListener('click', () =>
    draft('judge-prompt', 'judge', 'gen-domain-judge', 'gen-judge-status', null));

  // --- worked examples: a structured editor and the raw JSON side by side, both live on the
  // same object, so the nice view is never a lossy summary of what will actually be sent.
  let examples = fewShot.slice();
  const fsList = document.getElementById('fs-list');
  const tokens = (ex) => Math.round((ex.text.length + JSON.stringify(ex.records).length) / 4 / 100) / 10;
  const openExamples = new Set([0]);

  function columnsOf(ex) {
    const declared = [...rows.querySelectorAll('.f-name')].map(i => i.value.trim()).filter(Boolean);
    const seen = [...new Set(ex.records.flatMap(r => Object.keys(r)))].filter(c => c !== 'source_chunk_ids');
    return [...new Set([...declared, ...seen])];
  }

  function exampleHTML(ex, i) {
    const cols = columnsOf(ex);
    const open = openExamples.has(i);
    const body = !open ? '' : `
      <div class="body">
        <div class="fs-split">
          <div>
            <div class="row" style="margin-bottom:6px">
              <b style="font-size:.78rem">Records the model should produce</b>
              <span class="grow"></span>
              <button data-add-rec="${i}">+ record</button>
            </div>
            <div style="overflow-x:auto">
              <table class="ex-table"><thead><tr>
                ${cols.map(c => `<th>${esc(c)}</th>`).join('')}<th></th>
              </tr></thead><tbody>
                ${ex.records.map((r, ri) => `<tr>
                  ${cols.map(c => `<td><input data-ex="${i}" data-rec="${ri}" data-col="${esc(c)}"
                     value="${blank(r[c]) ? '' : esc(r[c])}"></td>`).join('')}
                  <td><button class="f-del" data-del-rec="${i}:${ri}" title="remove this record">&times;</button></td>
                </tr>`).join('') || `<tr><td colspan="${cols.length + 1}" class="muted">no records yet</td></tr>`}
              </tbody></table>
            </div>
            <details style="margin-top:8px"><summary class="muted">the paper text shown with it
              (${ex.text.length.toLocaleString()} characters)</summary>
              <textarea rows="8" data-text="${i}">${esc(ex.text)}</textarea></details>
          </div>
          <div>
            <div class="row" style="margin-bottom:6px">
              <b style="font-size:.78rem">Raw JSON</b>
              <span class="muted">edit either side</span>
              <span class="grow"></span>
              <button data-apply-json="${i}">Apply JSON</button>
            </div>
            <textarea class="ex-json" rows="18" data-json="${i}">${esc(JSON.stringify(ex, null, 2))}</textarea>
            <div class="muted" data-json-status="${i}"></div>
          </div>
        </div>
      </div>`;
    return `<div class="fs-item">
      <div class="head">
        <button data-toggle="${i}" class="linkish">${open ? '&#9662;' : '&#9656;'}</button>
        <b>Example ${i + 1}</b>
        <span class="muted">${esc(ex.source || 'added by hand')} &middot; ${ex.records.length} record(s)
          &middot; roughly ${tokens(ex)}k tokens per call</span>
        <span class="grow"></span>
        <button data-dup="${i}">duplicate</button>
        <button data-rm="${i}">remove</button>
      </div>
      ${body}
    </div>`;
  }

  function paintExamples() {
    document.getElementById('fs-count').textContent = examples.length
      ? `${examples.length} example(s) · roughly ${examples.reduce((n, e) => n + tokens(e), 0).toFixed(1)}k tokens added to every extraction call`
      : 'No examples — the model works from the prompt alone (zero-shot), which is often fine.';
    fsList.innerHTML = examples.map(exampleHTML).join('');

    fsList.querySelectorAll('[data-toggle]').forEach(b => b.addEventListener('click', () => {
      const i = Number(b.dataset.toggle);
      openExamples.has(i) ? openExamples.delete(i) : openExamples.add(i);
      paintExamples();
    }));
    fsList.querySelectorAll('[data-rm]').forEach(b => b.addEventListener('click', () => {
      examples.splice(Number(b.dataset.rm), 1);
      openExamples.clear();
      paintExamples();
    }));
    fsList.querySelectorAll('[data-dup]').forEach(b => b.addEventListener('click', () => {
      const i = Number(b.dataset.dup);
      examples.splice(i + 1, 0, JSON.parse(JSON.stringify(examples[i])));
      paintExamples();
    }));
    fsList.querySelectorAll('[data-add-rec]').forEach(b => b.addEventListener('click', () => {
      const i = Number(b.dataset.addRec);
      examples[i].records.push(Object.fromEntries(columnsOf(examples[i]).map(c => [c, null])));
      paintExamples();
    }));
    fsList.querySelectorAll('[data-del-rec]').forEach(b => b.addEventListener('click', () => {
      const [i, ri] = b.dataset.delRec.split(':').map(Number);
      examples[i].records.splice(ri, 1);
      paintExamples();
    }));
    // A cell edit updates the object, then repaints only the JSON pane -- repainting the whole
    // list would pull focus out of the field being typed in.
    fsList.querySelectorAll('input[data-ex]').forEach(input => input.addEventListener('change', () => {
      const i = Number(input.dataset.ex), ri = Number(input.dataset.rec), col = input.dataset.col;
      const raw = input.value.trim();
      const asNumber = raw !== '' && !Number.isNaN(Number(raw));
      examples[i].records[ri][col] = raw === '' ? null : (asNumber ? Number(raw) : raw);
      refreshJSON(i);
    }));
    fsList.querySelectorAll('textarea[data-text]').forEach(box => box.addEventListener('change', () => {
      const i = Number(box.dataset.text);
      examples[i].text = box.value;
      refreshJSON(i);
    }));
    fsList.querySelectorAll('[data-apply-json]').forEach(b => b.addEventListener('click', () => {
      const i = Number(b.dataset.applyJson);
      const box = fsList.querySelector(`textarea[data-json="${i}"]`);
      const status = fsList.querySelector(`[data-json-status="${i}"]`);
      try {
        const parsed = JSON.parse(box.value);
        if (typeof parsed.text !== 'string' || !parsed.text) throw new Error('needs a non-empty "text"');
        if (!Array.isArray(parsed.records)) throw new Error('needs a "records" array');
        examples[i] = parsed;
        paintExamples();
      } catch (e) {
        status.textContent = 'Not applied — ' + e.message;
        status.className = 'error';
      }
    }));
  }

  function refreshJSON(i) {
    const box = fsList.querySelector(`textarea[data-json="${i}"]`);
    if (box) box.value = JSON.stringify(examples[i], null, 2);
    document.getElementById('fs-count').textContent =
      `${examples.length} example(s) · roughly ${examples.reduce((n, e) => n + tokens(e), 0).toFixed(1)}k tokens added to every extraction call`;
  }
  paintExamples();

  document.getElementById('fs-add').addEventListener('click', () => say('fs-add-status', async () => {
    const id = document.getElementById('fs-source').value;
    if (!id) throw new Error('extract a paper first — there is nothing to build an example from');
    const [paper, extraction] = await Promise.all([get('/api/papers/' + id), get(`/api/papers/${id}/extraction`)]);
    if (!extraction.records.length) throw new Error('that paper produced no records');
    examples.push({
      text: paper.chunks.map(c => (paper.source_tracking ? `ID: ${c.id}\n` : '') + c.text).join('\n\n'),
      records: extraction.records,
      source: paper.filename,
    });
    openExamples.add(examples.length - 1);
    paintExamples();
    return 'Added below — press "Save all examples" to keep it.';
  }));

  document.getElementById('fs-add-blank').addEventListener('click', () => {
    examples.push({ text: '', records: [], source: null });
    openExamples.add(examples.length - 1);
    paintExamples();
    document.getElementById('fs-add-status').textContent = 'Empty example added — fill it in below.';
  });

  on('save-few-shot', 'few-shot-status', () =>
    put('/api/few-shot', examples).then(r => `Saved ${r.length} example(s).`));

  // --- defaults
  on('save-defaults', 'defaults-status', () => put('/api/settings', {
    source_tracking_default: document.getElementById('src-default').checked,
  }).then(() => 'Saved.'));
}

// ---------- boot ----------

get('/api/settings').then(s => { document.getElementById('model-badge').textContent = 'model: ' + s.model; });
router();
