/* DiagSafe dataset dashboard — vanilla JS, no build step.

   Two data sources, same UI:
     api    — FastAPI backend (python dashboard/app.py)
     static — pre-generated JSON under data/ (static hosting, see export.py).
              Rubrics are chunked and fetched only when a sample is opened.
*/

const STATIC = window.DIAGSAFE_STATIC === true;
const PAGE_SIZE = 60;

const state = {
  view: 'overview',
  filters: { q: '', language: '', subset: '', turns: '', label: '', offset: 0 },
  list: [],
  activeId: null,
  tab: 'prompt',
  labels: [],
  standards: [],
  standardKey: null,
  standardLang: 'en',
};

const store = {
  prompts: [], standards: [], meta: {}, labels: [],
  rubricIndex: null, rubricChunks: {}, byId: new Map(), byLabel: new Map(),
};

const $ = (selector) => document.querySelector(selector);
const fmt = (value) => (value ?? 0).toLocaleString('en-US');
const pct = (value) => `${(value * 100).toFixed(1)}%`;

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text ?? '';
  return div.innerHTML;
}

async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}

function showNotice(message) {
  const notice = $('#notice');
  notice.textContent = message;
  notice.hidden = false;
}

/* ---------- data layer ---------- */

async function initStore() {
  if (!STATIC) return;
  const [prompts, standards, meta] = await Promise.all([
    getJson('data/prompts.json'),
    getJson('data/standards.json'),
    getJson('data/meta.json'),
  ]);
  store.prompts = prompts;
  store.standards = standards;
  store.meta = meta;
  store.labels = meta.labels || [];
  store.rubricIndex = await getJson('data/rubrics/index.json');
  store.byId = new Map(prompts.map((item) => [item.id, item]));
  store.byLabel = new Map(standards.map((item) => [item.key, item]));
}

async function rubricOf(sampleId) {
  const file = (store.rubricIndex.map || {})[sampleId];
  if (!file) return '';
  if (!store.rubricChunks[file]) {
    store.rubricChunks[file] = await getJson(`data/rubrics/${file}`);
  }
  return store.rubricChunks[file][sampleId] || '';
}

const fetchSummary = () => (STATIC ? store.meta.summary : getJson('/api/summary'));
const fetchStats = () => (STATIC ? store.meta.stats : getJson('/api/stats'));
const fetchStandards = () => (STATIC ? store.standards : getJson('/api/standards'));
const fetchLabels = () => (STATIC ? store.labels : getJson('/api/labels'));

async function fetchSamples(filters) {
  if (!STATIC) {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    return getJson(`/api/samples?${params.toString()}`);
  }
  const needle = (filters.q || '').trim().toLowerCase();
  const matched = store.prompts.filter((item) => {
    if (filters.language && item.language !== filters.language) return false;
    if (filters.subset && item.subset !== filters.subset) return false;
    if (filters.turns === 'single' && item.n_turns !== 1) return false;
    if (filters.turns === 'multi' && item.n_turns <= 1) return false;
    if (filters.label && item.l3 !== filters.label) return false;
    if (needle) {
      const haystack = item.id.toLowerCase() + ' '
        + item.messages.map((message) => message.content).join(' ').toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    return true;
  });
  const offset = filters.offset || 0;
  const limit = filters.limit || PAGE_SIZE;
  return { total: matched.length, offset, items: matched.slice(offset, offset + limit) };
}

async function fetchSample(sampleId) {
  if (!STATIC) return getJson(`/api/samples/${encodeURIComponent(sampleId)}`);
  const row = store.byId.get(sampleId);
  if (!row) throw new Error(`Unknown sample: ${sampleId}`);
  return {
    ...row,
    standard: store.byLabel.get(row.l3) || null,
    rubric: await rubricOf(sampleId),
  };
}

/* ---------- charts ---------- */

function barRow(label, value, total, alt = false) {
  const share = total ? (value / total) * 100 : 0;
  const shown = share > 0 && share < 0.1 ? '<0.1%' : `${share.toFixed(1)}%`;
  const width = Math.max(share, share > 0 ? 1.2 : 0);
  return `
    <div class="bar-row">
      <span class="bar-label">${escapeHtml(label)}</span>
      <span class="bar-value">${fmt(value)}${total ? ` · ${shown}` : ''}</span>
      <span class="bar-track"><span class="bar-fill${alt ? ' alt' : ''}" style="width:${width}%"></span></span>
    </div>`;
}

const DONUT_PALETTE = ['#131315', '#7a7f88', '#c4c6c1'];

function donutCard(entries) {
  /* SVG donut for small category counts (2–3). Arc lengths are exact: the last
     slice closes the ring so floating-point error cannot leak past a joint, and
     the primary slice paints last so it covers any sub-pixel overlap. */
  const total = entries.reduce((sum, entry) => sum + entry.value, 0) || 1;
  const radius = 46;
  const circumference = 2 * Math.PI * radius;
  const lengths = entries.map((entry) => (entry.value / total) * circumference);
  lengths[lengths.length - 1] = Math.max(
    circumference - lengths.slice(0, -1).reduce((sum, value) => sum + value, 0), 0);
  const offsets = [];
  let accumulated = 0;
  for (const length of lengths) { offsets.push(accumulated); accumulated += length; }
  const arcs = entries
    .map((_, index) => index).reverse()
    .map((index) => `
      <circle class="donut-arc" cx="60" cy="60" r="${radius}"
        style="stroke:${DONUT_PALETTE[index % DONUT_PALETTE.length]};
          stroke-dasharray:${lengths[index]} ${circumference - lengths[index]};
          stroke-dashoffset:${-offsets[index]};"/>`)
    .join('');
  const legend = entries.map((entry, index) => {
    const share = (entry.value / total) * 100;
    const shown = share > 0 && share < 0.1 ? '<0.1%' : `${share.toFixed(1)}%`;
    return `
      <div>
        <span class="donut-swatch" style="background:${DONUT_PALETTE[index % DONUT_PALETTE.length]}"></span>
        <span>${escapeHtml(entry.label)}</span>
        <span class="donut-value">${fmt(entry.value)} · ${shown}</span>
      </div>`;
  }).join('');
  return `
    <div class="donut-wrap">
      <svg class="donut" viewBox="0 0 120 120" role="img" aria-label="${escapeHtml(entries.map((e) => e.label).join(' vs '))}">
        <circle class="donut-track" cx="60" cy="60" r="${radius}"/>
        ${arcs}
      </svg>
      <div class="donut-legend">${legend}</div>
    </div>`;
}

/* ---------- navigation ---------- */

function setView(view) {
  state.view = view;
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.classList.toggle('is-active', item.dataset.view === view);
  });
  document.querySelectorAll('.view').forEach((section) => {
    section.classList.toggle('is-active', section.dataset.view === view);
  });
  $('#crumb').textContent = {
    overview: 'Overview', standards: 'Standards', explore: 'Prompts & rubrics',
  }[view] || view;
  window.scrollTo({ top: 0 });
}

/* ---------- overview ---------- */

async function renderOverview() {
  const [summary, stats] = await Promise.all([fetchSummary(), fetchStats()]);

  $('#source-badge').textContent = `${summary.files.prompts} · ${summary.taxonomy.l3} labels`;

  $('#side-facts').innerHTML = [
    ['Prompts', fmt(summary.prompts)],
    ['Rubrics', fmt(summary.rubrics)],
    ['L1 / L2 / L3', `${summary.taxonomy.l1} / ${summary.taxonomy.l2} / ${summary.taxonomy.l3}`],
    ['Languages', `${fmt(summary.languages.en)} EN · ${fmt(summary.languages.zh)} ZH`],
    ['Single / Multi', `${fmt(summary.turns.single)} / ${fmt(summary.turns.multi)}`],
  ].map(([key, value]) => `<div><dt>${key}</dt><dd>${value}</dd></div>`).join('');

  const total = summary.prompts;
  $('#kpi-grid').innerHTML = [
    ['Prompts', fmt(total)],
    ['Prompt-level rubrics', fmt(summary.rubrics)],
    ['Taxonomy labels', fmt(summary.taxonomy.l3)],
    ['First-level dimensions', fmt(summary.taxonomy.l1)],
    ['Chinese prompts', fmt(summary.languages.zh)],
    ['Multi-turn prompts', fmt(summary.turns.multi)],
  ].map(([label, value]) => `
    <div class="kpi"><div class="kpi-value">${value}</div><div class="kpi-label">${label}</div></div>
  `).join('');

  // Dialogue length collapses to 1 / 2 / 3+ turns: the 4- and 5-turn groups
  // hold 20 and 1 prompts, too thin to read as separate donut slices.
  const turnsBy = Object.fromEntries(stats.by_turns.map((row) => [row.turns, row.count]));
  const turnBuckets = [
    { label: '1 turn', value: turnsBy[1] || 0 },
    { label: '2 turns', value: turnsBy[2] || 0 },
    { label: '3+ turns', value: stats.by_turns.filter((row) => row.turns >= 3)
        .reduce((sum, row) => sum + row.count, 0) },
  ];

  $('#composition').innerHTML = `
    <div class="card"><div class="card-title">Language</div>
      ${donutCard([
        { label: 'English', value: summary.languages.en },
        { label: 'Chinese', value: summary.languages.zh },
      ])}</div>
    <div class="card"><div class="card-title">Subset</div>
      ${donutCard([
        { label: 'DiagBase', value: summary.subsets.DiagBase },
        { label: 'DiagAttack', value: summary.subsets.DiagAttack },
      ])}</div>
    <div class="card"><div class="card-title">Dialogue length</div>
      ${donutCard(turnBuckets)}</div>`;
}

/* ---------- standards ---------- */

/* Taxonomy names in the selected language. English uses the label slugs;
   Chinese falls back to English when a name is missing. */
function namesOf(item, lang = state.standardLang) {
  const value = item || {};
  if (lang === 'zh') {
    return {
      l1: value.l1_zh || value.l1_en || '',
      l2: value.l2_zh || value.l2_en || '',
      l3: value.l3_zh || value.l3_en || '',
    };
  }
  return { l1: value.l1_en || '', l2: value.l2_en || '', l3: value.l3_en || '' };
}

function standardFields(item, lang = state.standardLang) {
  const value = item || {};
  const zh = lang === 'zh';
  const pick = (en, zhValue) => (zh ? (zhValue || en) : (en || zhValue)) || '—';
  const titles = zh
    ? ['定义', '标准总则', '标准细则']
    : ['Definition', 'General standard', 'Detailed rules'];
  const bodies = [
    pick(value.definition, value.definition_zh),
    pick(value.general_standard, value.general_standard_zh),
    pick(value.detailed_rules, value.detailed_rules_zh),
  ];
  return titles.map((title, index) => `
    <div class="field"><div class="field-title">${title}</div>
      <div class="field-body">${escapeHtml(bodies[index])}</div></div>`).join('');
}

function langTabs(lang = state.standardLang) {
  return `
    <div class="tabs">
      <button class="tab${lang === 'zh' ? '' : ' is-active'}" data-lang="en">English</button>
      <button class="tab${lang === 'zh' ? ' is-active' : ''}" data-lang="zh">中文</button>
    </div>`;
}

async function renderStandards() {
  state.standards = await fetchStandards();
  const codes = [...new Set(state.standards.map((item) => item.code))].sort();
  $('#s-dimension').innerHTML = '<option value="">All dimensions</option>' + codes
    .map((code) => {
      const sample = state.standards.find((item) => item.code === code);
      return `<option value="${escapeHtml(code)}">${escapeHtml(code)} · ${escapeHtml(sample.l1_en)}</option>`;
    }).join('');
  renderStandardList('');
  $('#s-search').addEventListener('input', () => renderStandardList($('#s-search').value));
  $('#s-dimension').addEventListener('change', () => renderStandardList($('#s-search').value));
}

function renderStandardList(needle) {
  const query = needle.trim().toLowerCase();
  const code = $('#s-dimension').value;
  const rows = (state.standards || []).filter((item) => {
    if (code && item.code !== code) return false;
    return !query || [
      item.code, item.l1_en, item.l2_en, item.l3_en, item.l1_zh, item.l2_zh, item.l3_zh,
    ].join(' ').toLowerCase().includes(query);
  });

  // L1 -> L2 -> L3; rows arrive in taxonomy order, so each L2 group is contiguous.
  const groups = new Map();
  rows.forEach((item) => {
    if (!groups.has(item.code)) groups.set(item.code, { item, children: new Map() });
    const children = groups.get(item.code).children;
    if (!children.has(item.l2)) children.set(item.l2, { item, items: [] });
    children.get(item.l2).items.push(item);
  });

  $('#standards-total').textContent = fmt(rows.length);
  $('#standards-list').innerHTML = [...groups.entries()].map(([groupCode, group]) => `
    <div class="std-group">
      <div class="std-group-head"><span class="tax-code">${escapeHtml(groupCode)}</span>${escapeHtml(namesOf(group.item).l1)}</div>
      ${[...group.children.values()].map((sub) => `
        <div class="std-sub-head">${escapeHtml(namesOf(sub.item).l2)}</div>
        ${sub.items.map((item) => `
          <div class="std-item${item.key === state.standardKey ? ' is-active' : ''}" data-key="${escapeHtml(item.key)}">
            <span>${escapeHtml(namesOf(item).l3)}</span>
            <span class="donut-value">${item.count}</span>
          </div>`).join('')}`).join('')}
    </div>`).join('') || '<div class="placeholder">No label matches.</div>';

  document.querySelectorAll('.std-item').forEach((node) => {
    node.addEventListener('click', () => showStandard(node.dataset.key));
  });
}

function showStandard(key) {
  const item = (state.standards || []).find((entry) => entry.key === key);
  if (!item) return;
  state.standardKey = key;
  const names = namesOf(item);
  document.querySelectorAll('.std-item').forEach((node) => {
    node.classList.toggle('is-active', node.dataset.key === key);
  });

  $('#standard-pane').innerHTML = `
    <div class="detail-head">
      <div class="detail-id">${escapeHtml(names.l3)}</div>
      <div class="pill-row">
        <span class="pill accent">${escapeHtml(item.code)}</span>
        <span class="pill">${fmt(item.count)} prompts</span>
      </div>
      <div class="muted" style="font-size:13px">${escapeHtml(names.l1)} › ${escapeHtml(names.l2)}</div>
      <div><button class="button" id="std-jump" data-key="${escapeHtml(item.key)}">View prompts →</button></div>
    </div>
    ${langTabs()}
    <div class="tab-body">${standardFields(item)}</div>`;

  $('#std-jump').addEventListener('click', () => {
    state.filters.label = item.key;
    state.filters.offset = 0;
    $('#f-label').value = item.key;
    setView('explore');
    loadList();
  });
  document.querySelectorAll('#standard-pane .tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      state.standardLang = tab.dataset.lang;
      renderStandardList($('#s-search').value);
      showStandard(key);
    });
  });
}

/* ---------- prompts ---------- */

async function loadList() {
  const data = await fetchSamples({ ...state.filters, limit: PAGE_SIZE });
  state.list = data.items;
  $('#list-total').textContent = `${fmt(data.total)} samples`;
  const start = data.total ? data.offset + 1 : 0;
  $('#list-range').textContent = `showing ${fmt(start)}–${fmt(data.offset + data.items.length)}`;
  $('#prev-page').disabled = data.offset <= 0;
  $('#next-page').disabled = data.offset + data.items.length >= data.total;

  $('#sample-list').innerHTML = data.items.map((item) => `
    <div class="sample-item${item.id === state.activeId ? ' is-active' : ''}" data-id="${escapeHtml(item.id)}">
      <div class="sample-top">
        <span class="sample-id">${escapeHtml(item.id)}</span>
        <span class="pill${item.subset === 'DiagAttack' ? ' accent' : ''}">${escapeHtml(item.subset)}</span>
      </div>
      <div class="sample-preview">${escapeHtml(item.preview)}</div>
      <div class="pill-row">
        <span class="pill">${item.language === 'zh' ? 'Chinese' : 'English'}</span>
        <span class="pill">${item.n_turns} turn${item.n_turns > 1 ? 's' : ''}</span>
      </div>
    </div>`).join('');

  document.querySelectorAll('.sample-item').forEach((node) => {
    node.addEventListener('click', () => openSample(node.dataset.id, node));
  });
}

async function openSample(sampleId, node) {
  state.activeId = sampleId;
  state.tab = 'prompt';
  document.querySelectorAll('.sample-item').forEach((item) => {
    item.classList.toggle('is-active', item.dataset.id === sampleId);
  });
  if (node) node.scrollIntoView({ block: 'nearest' });

  const sample = await fetchSample(sampleId);
  const standard = sample.standard || {};
  const facts = [
    `<span class="pill accent">${escapeHtml(sample.subset)}</span>`,
    `<span class="pill">${sample.language === 'zh' ? 'Chinese' : 'English'}</span>`,
    `<span class="pill">${sample.n_turns} turn${sample.n_turns > 1 ? 's' : ''}</span>`,
    `<span class="pill">${escapeHtml(standard.code || sample.category.l1 || '')}</span>`,
  ];

  $('#detail-pane').innerHTML = `
    <div class="detail-head">
      <div class="detail-id">${escapeHtml(sample.id)}</div>
      <div class="pill-row">${facts.join('')}</div>
      <div class="muted" style="font-size:13px">
        ${escapeHtml(standard.l1_en || '')} › ${escapeHtml(standard.l2_en || '')} › <b>${escapeHtml(standard.l3_en || '')}</b>
      </div>
    </div>
    <div class="tabs">
      <button class="tab is-active" data-tab="prompt">Prompt</button>
      <button class="tab" data-tab="rubric">Rubric</button>
      <button class="tab" data-tab="standard">Standard</button>
    </div>
    <div class="tab-body" id="tab-body"><div class="placeholder">Loading…</div></div>`;

  document.querySelectorAll('#detail-pane .tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      state.tab = tab.dataset.tab;
      document.querySelectorAll('#detail-pane .tab').forEach((other) => {
        other.classList.toggle('is-active', other.dataset.tab === state.tab);
      });
      renderTab(sample);
    });
  });
  renderTab(sample);
}

function renderTab(sample) {
  const body = $('#tab-body');
  const standard = sample.standard || {};

  if (state.tab === 'prompt') {
    body.innerHTML = sample.messages.map((message, index) => `
      <div class="turn">
        <div class="turn-head">TURN ${index + 1} · ${escapeHtml(message.role.toUpperCase())}</div>
        <div class="turn-body">${escapeHtml(message.content)}</div>
      </div>`).join('') || '<div class="placeholder">No messages.</div>';
    return;
  }

  if (state.tab === 'rubric') {
    body.innerHTML = sample.rubric
      ? `<div class="field">
           <div class="field-title">Judge prompt template</div>
           <div class="rubric-raw">${escapeHtml(sample.rubric)}</div>
         </div>`
      : '<div class="placeholder">This sample has no rubric.</div>';
    return;
  }

  const names = namesOf(standard);
  const zh = state.standardLang === 'zh';
  body.innerHTML = `
    <div class="lang-switch">
      <button class="chip${zh ? '' : ' is-active'}" data-lang="en">English</button>
      <button class="chip${zh ? ' is-active' : ''}" data-lang="zh">中文</button>
    </div>
    <div class="field"><div class="field-title">${zh ? '标签路径' : 'Path'}</div>
      <div class="field-body">${escapeHtml(names.l1)} › ${escapeHtml(names.l2)} › ${escapeHtml(names.l3)}</div></div>
    ${standardFields(standard)}`;
  body.querySelectorAll('.lang-switch .chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      state.standardLang = chip.dataset.lang;
      renderTab(sample);
    });
  });
}

/* ---------- bootstrap ---------- */

async function init() {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.addEventListener('click', () => setView(item.dataset.view));
  });

  await initStore();

  const labels = await fetchLabels();
  state.labels = labels;
  $('#f-label').innerHTML = '<option value="">All labels</option>' + labels
    .map((label) => `<option value="${escapeHtml(label.l3)}">${escapeHtml(label.l3_en)} (${escapeHtml(label.l1)})</option>`)
    .join('');

  const bind = (selector, key) => {
    $(selector).addEventListener('input', () => {
      state.filters[key] = $(selector).value;
      state.filters.offset = 0;
      loadList().catch((error) => showNotice(error.message));
    });
  };
  bind('#f-q', 'q');
  bind('#f-language', 'language');
  bind('#f-subset', 'subset');
  bind('#f-turns', 'turns');
  bind('#f-label', 'label');

  $('#f-reset').addEventListener('click', () => {
    state.filters = { q: '', language: '', subset: '', turns: '', label: '', offset: 0 };
    ['#f-q', '#f-language', '#f-subset', '#f-turns', '#f-label'].forEach((selector) => {
      $(selector).value = '';
    });
    loadList().catch((error) => showNotice(error.message));
  });

  $('#prev-page').addEventListener('click', () => {
    state.filters.offset = Math.max(state.filters.offset - PAGE_SIZE, 0);
    loadList().catch((error) => showNotice(error.message));
  });
  $('#next-page').addEventListener('click', () => {
    state.filters.offset += PAGE_SIZE;
    loadList().catch((error) => showNotice(error.message));
  });

  await Promise.all([
    renderOverview(),
    renderStandards(),
    loadList(),
  ]);
}

init().catch((error) => showNotice(`Failed to load data: ${error.message}`));
