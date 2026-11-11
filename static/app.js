const $ = (id) => document.getElementById(id);

const viewer = new BpmnJS({ container: '#canvas' });
let current = null;
let activeFilter = 'all';
let activeFinding = null;

const band = (score) => (score >= 90 ? 'good' : score >= 70 ? 'mid' : 'bad');

const TIER_LABEL = {
  structural: 'Structural validity',
  convention: 'Modelling conventions',
  framework: 'Framework alignment',
};

/* ---------- intake ---------- */

document.querySelectorAll('[data-sample]').forEach((chip) => {
  chip.addEventListener('click', async () => {
    const response = await fetch(`/api/sample/${chip.dataset.sample}`);
    const data = await response.json();
    $('document').value = data.text || '';
    $('file').value = '';
    $('filename').textContent = '';
    setStatus(`Loaded ${chip.dataset.sample}. Analyse when ready.`);
  });
});

$('file').addEventListener('change', () => {
  const file = $('file').files[0];
  $('filename').textContent = file ? file.name : '';
  if (file) setStatus(`${file.name} ready to analyse.`);
});

const intake = $('intake');
['dragenter', 'dragover'].forEach((event) =>
  intake.addEventListener(event, (e) => {
    e.preventDefault();
    intake.classList.add('is-dragover');
  })
);
['dragleave', 'drop'].forEach((event) =>
  intake.addEventListener(event, (e) => {
    e.preventDefault();
    intake.classList.remove('is-dragover');
  })
);
intake.addEventListener('drop', (e) => {
  const file = e.dataTransfer.files[0];
  if (!file) return;
  const transfer = new DataTransfer();
  transfer.items.add(file);
  $('file').files = transfer.files;
  $('filename').textContent = file.name;
  setStatus(`${file.name} ready to analyse.`);
});

function setStatus(message, isError = false) {
  const status = $('status');
  status.textContent = message;
  status.classList.toggle('is-error', isError);
}

$('run').addEventListener('click', analyse);

async function analyse() {
  const file = $('file').files[0];
  const text = $('document').value.trim();
  if (!file && !text) {
    setStatus('Paste a policy document or choose a file first.', true);
    return;
  }

  const button = $('run');
  button.disabled = true;
  setStatus('Extracting the process model…');

  const body = new FormData();
  if (file) body.append('file', file);
  else body.append('text', text);

  try {
    const response = await fetch('/api/analyse', { method: 'POST', body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Analysis failed.');
    current = data;
    await render(data);
    setStatus(
      `Modelled ${countActivities(data.spec)} activities via the ` +
        `${data.method === 'llm' ? 'language model' : 'deterministic parser'}. ` +
        `${data.report.counts.errors} errors, ${data.report.counts.warnings} warnings.`
    );
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    button.disabled = false;
  }
}

const countActivities = (spec) =>
  spec.nodes.filter((n) => !n.kind.includes('Event') && !n.kind.includes('Gateway')).length;

/* ---------- render ---------- */

async function render(data) {
  $('results').hidden = false;
  $('process-name').textContent = data.spec.name;

  const score = data.report.score;
  $('score').textContent = score;
  const verdict = $('verdict');
  verdict.textContent = data.report.verdict;
  verdict.dataset.band = band(score);

  $('tiers').innerHTML = Object.entries(data.report.tiers)
    .map(
      ([tier, value]) => `
      <div>
        <div class="tier-label">
          <span>${TIER_LABEL[tier] || tier}</span>
          <b>${value.score}</b>
        </div>
        <div class="bar"><span data-band="${band(value.score)}" style="width:${value.score}%"></span></div>
      </div>`
    )
    .join('');

  const c = data.classification;
  $('classification').innerHTML = `
    <div>
      <dt>Framework element</dt>
      <dd>${c.pcf_id ? `<code>${c.pcf_id}</code> ${escapeHtml(c.pcf_name)}` : 'Unclassified'}
        ${c.pcf_id ? `<br><span class="element">confidence ${Math.round(c.pcf_confidence * 100)}%${c.pcf_official ? '' : ' · working taxonomy'}</span>` : ''}
      </dd>
    </div>
    <div>
      <dt>ITIL 4 practice</dt>
      <dd>${c.itil_practice ? escapeHtml(c.itil_practice) : 'Unmapped'}</dd>
    </div>
    <div>
      <dt>Process owner</dt>
      <dd>${escapeHtml(data.spec.owner || 'Not stated in source')}</dd>
    </div>`;

  ['bpmn', 'xml', 'xlsx', 'md', 'json'].forEach((kind) => {
    $(`dl-${kind}`).href = `/download/${data.key}.${kind}`;
  });

  try {
    await viewer.importXML(data.bpmn);
    viewer.get('canvas').zoom('fit-viewport', 'auto');
  } catch (error) {
    setStatus(`Model generated but could not be rendered: ${error.message}`, true);
  }

  renderFindings();
  $('results').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderFindings() {
  const list = $('finding-list');
  const findings = current.report.findings.filter(
    (f) => activeFilter === 'all' || f.severity === activeFilter
  );

  if (!findings.length) {
    list.innerHTML = `<li class="empty">No ${activeFilter === 'all' ? '' : activeFilter + ' '}findings. This model meets every rule in that set.</li>`;
    return;
  }

  list.innerHTML = findings
    .map(
      (f, index) => `
      <li data-index="${index}" data-element="${escapeHtml(f.element_id)}" data-severity="${f.severity}">
        <span class="sev" data-s="${f.severity}">${f.severity}</span>
        <span class="rule">${escapeHtml(f.rule)}<small>${f.tier}</small></span>
        <div class="finding-body">
          <p>${escapeHtml(f.message)}</p>
          ${f.element_name ? `<p class="element">${escapeHtml(f.element_name)}</p>` : ''}
          ${f.remediation ? `<p class="fix">${escapeHtml(f.remediation)}</p>` : ''}
        </div>
      </li>`
    )
    .join('');

  list.querySelectorAll('li[data-element]').forEach((row) => {
    row.addEventListener('click', () => highlight(row));
  });
}

function highlight(row) {
  const canvas = viewer.get('canvas');
  const registry = viewer.get('elementRegistry');

  if (activeFinding) {
    activeFinding.row.classList.remove('is-active');
    if (activeFinding.elementId && registry.get(activeFinding.elementId)) {
      canvas.removeMarker(activeFinding.elementId, activeFinding.marker);
    }
  }

  const elementId = row.dataset.element;
  const marker = row.dataset.severity === 'error' ? 'op-flagged' : 'op-flagged-warning';
  row.classList.add('is-active');

  if (elementId && registry.get(elementId)) {
    canvas.addMarker(elementId, marker);
    canvas.scrollToElement(elementId, { top: 180, bottom: 180, left: 180, right: 180 });
    activeFinding = { row, elementId, marker };
  } else {
    // process-level findings have no element to point at
    activeFinding = { row, elementId: null, marker };
  }
}

$('filters').addEventListener('click', (event) => {
  const button = event.target.closest('.filter');
  if (!button || !current) return;
  document.querySelectorAll('.filter').forEach((b) => b.classList.remove('is-on'));
  button.classList.add('is-on');
  activeFilter = button.dataset.severity;
  activeFinding = null;
  renderFindings();
});

$('fit').addEventListener('click', () => viewer.get('canvas').zoom('fit-viewport', 'auto'));
$('zoom-in').addEventListener('click', () => viewer.get('zoomScroll').stepZoom(1));
$('zoom-out').addEventListener('click', () => viewer.get('zoomScroll').stepZoom(-1));

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])
  );
}
