import { getApiToken, setApiToken } from './js/state.js';
import {
  apiJson as apiJsonBase,
  apiUploadRun,
  apiJobs,
  apiJob,
  apiJobLogs,
  apiCancelJob,
} from './js/api.js';
import { toast } from './js/components/toast.js';
import { initCatalogView } from './js/views/catalog.js';

function fmtTs(ts) {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toISOString().replace("T", " ").replace("Z", "Z");
}

function esc(s) {
  return (s ?? "").toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
function setAuthStatus(msg) {
  const el = document.getElementById('authStatus');
  if (!el) return;
  el.textContent = msg || '(no token)';
}

function $(id) {
  return document.getElementById(id);
}

function logLine(msg) {
  const box = $("logBox");
  const ts = new Date().toISOString();
  box.textContent += `[${ts}] ${msg}\n`;
  box.scrollTop = box.scrollHeight;
}

function logCmdResult(res) {
  logLine(`CMD (${res.exit_code}) [cwd=${res.cwd}] ${res.cmd.join(' ')}`);
  if (res.stdout && res.stdout.trim()) {
    logLine(`stdout:\n${res.stdout.trim()}`);
  }
  if (res.stderr && res.stderr.trim()) {
    logLine(`stderr:\n${res.stderr.trim()}`);
  }
}

function renderStateBadges(st) {
  const host = document.getElementById('stateBadges');
  if (!host) return;
  host.innerHTML = '';
  if (!st) return;

  const items = [
    { label: st.multi_tenant ? 'multi-tenant' : 'single-tenant', tone: st.multi_tenant ? 'warn' : 'ok' },
    { label: 'uploads', tone: st.uploads_dir ? 'ok' : 'warn' },
    { label: 'bundles', tone: st.bundles_dir ? 'ok' : 'warn' },
  ];

  for (const it of items) {
    const b = document.createElement('span');
    b.className = `badge badge-${it.tone}`;
    b.textContent = it.label;
    host.appendChild(b);
  }
}

const _apiHooks = {
  onAuthError: () => {
    setAuthStatus('auth required (401/403). Set API token and retry.');
    toast('Auth required (401/403).', { kind: 'error' });
  },
};

async function apiJson(path, options) {
  return await apiJsonBase(path, options, _apiHooks);
}

function setEnabled(el, enabled) {
  el.disabled = !enabled;
}

async function withDisabled(el, fn) {
  const prev = !!el.disabled;
  el.disabled = true;
  try {
    return await fn();
  } finally {
    el.disabled = prev;
  }
}

function selectedBundlePath() {
  const sel = $("bundleSelect");
  if (!sel.value) return null;
  return sel.value;
}

let cy = null;

let _runsById = new Map();

function shortId(id) {
  if (!id) return '';
  const s = String(id);
  return s.length > 34 ? s.slice(0, 34) + '…' : s;
}

function _setText(id, text) {
  const el = $(id);
  if (!el) return;
  el.textContent = text;
}

function _selectedRunId() {
  const sel = $('runSelect');
  if (!sel) return null;
  const v = (sel.value || '').trim();
  return v ? v : null;
}

function _renderRunContext(runId) {
  if (!runId) {
    _setText('selectedRunId', '(all)');
    _setText('selectedTraceIds', '(n/a)');
    return;
  }
  const r = _runsById.get(runId) || null;
  _setText('selectedRunId', runId);
  if (r && Array.isArray(r.trace_ids) && r.trace_ids.length > 0) {
    const shown = r.trace_ids.slice(0, 6).map(t => shortId(t));
    const more = r.trace_ids.length > shown.length ? ` (+${r.trace_ids.length - shown.length})` : '';
    _setText('selectedTraceIds', shown.join(', ') + more);
  } else {
    _setText('selectedTraceIds', '(none)');
  }
}

function _fmtDeltaLine(e) {
  const h = (e && e.event_hash ? String(e.event_hash) : '').slice(0, 12);
  const prev = (e && e.prev_hash ? String(e.prev_hash) : '').slice(0, 12);
  const ops = (e && e.ops_hash ? String(e.ops_hash) : '').slice(0, 12);
  const src = e && e.source ? String(e.source) : '';
  const ctx = e && e.context_node_id ? shortId(e.context_node_id) : '';
  const run = e && e.run_id ? shortId(e.run_id) : '';
  const trace = e && e.trace_id ? shortId(e.trace_id) : '';
  return `${h} prev=${prev} src=${src} ctx=${ctx} run=${run} trace=${trace} ops=${ops}`.trim();
}

async function refreshRunsUI() {
  const sel = $('runSelect');
  if (!sel) return;
  const prev = _selectedRunId();

  const data = await apiJson('/api/runs?limit=200');
  const runs = (data && data.runs) ? data.runs : [];

  _runsById = new Map();
  for (const r of runs) {
    if (r && r.run_id) _runsById.set(String(r.run_id), r);
  }

  sel.innerHTML = '';
  const optAll = document.createElement('option');
  optAll.value = '';
  optAll.textContent = '(all)';
  sel.appendChild(optAll);

  for (const r of runs) {
    const rid = r && r.run_id ? String(r.run_id) : '';
    if (!rid) continue;
    const opt = document.createElement('option');
    opt.value = rid;
    const nEvents = (r && typeof r.events === 'number') ? r.events : null;
    opt.textContent = nEvents != null ? `${shortId(rid)}  (${nEvents} events)` : shortId(rid);
    sel.appendChild(opt);
  }

  if (prev && _runsById.has(prev)) {
    sel.value = prev;
  } else {
    sel.value = '';
  }
  _renderRunContext(_selectedRunId());
}

async function loadDeltasUI() {
  const pre = $('deltasPre');
  if (!pre) return;
  const runId = _selectedRunId();
  const qs = new URLSearchParams();
  qs.set('limit', '200');
  if (runId) qs.set('run_id', runId);
  const data = await apiJson('/api/deltas?' + qs.toString());
  const events = (data && data.events) ? data.events : [];
  if (!events || events.length === 0) {
    pre.textContent = '(none)';
    return;
  }
  pre.textContent = events.map(_fmtDeltaLine).join('\n');
}

function ensureCy() {
  if (cy) return cy;
  const container = document.getElementById('cy');
  if (!container) throw new Error('Missing #cy container');
  if (!window.cytoscape) throw new Error('Cytoscape not loaded');

  cy = window.cytoscape({
    container,
    elements: [],
    style: [
      {
        selector: 'node',
        style: {
          'background-color': 'ButtonFace',
          'border-color': 'GrayText',
          'border-width': 1,
          'label': 'data(label)',
          'color': 'CanvasText',
          'font-size': 9,
          'text-valign': 'center',
          'text-halign': 'center',
          'text-wrap': 'ellipsis',
          'text-max-width': 160
        }
      },
      {
        selector: 'node[isCenter = 1]',
        style: {
          'border-color': 'Highlight',
          'border-width': 3
        }
      },
      {
        selector: 'edge',
        style: {
          'curve-style': 'bezier',
          'width': 1,
          'line-color': 'GrayText',
          'target-arrow-color': 'GrayText',
          'target-arrow-shape': 'triangle',
          'label': 'data(type)',
          'font-size': 7,
          'color': 'CanvasText',
          'text-background-opacity': 1,
          'text-background-color': 'Canvas',
          'text-background-padding': '2px',
          'text-rotation': 'autorotate'
        }
      }
    ],
    layout: { name: 'grid' }
  });

  const inspector = $('inspectorPre');
  function setInspector(obj) {
    if (!inspector) return;
    if (!obj) {
      inspector.textContent = 'Select a node/edge to inspect.';
      return;
    }
    inspector.textContent = JSON.stringify(obj, null, 2);
  }

  cy.on('select', 'node', (evt) => {
    const d = evt.target.data();
    setInspector({
      kind: 'node',
      id: d.id,
      type: d.type,
      attrs: d.attrs ?? null
    });
  });

  cy.on('select', 'edge', (evt) => {
    const d = evt.target.data();
    setInspector({
      kind: 'edge',
      id: d.id,
      src: d.source,
      dst: d.target,
      type: d.type,
      attention_score: d.attention_score ?? null,
      attrs: d.attrs ?? null
    });
  });

  cy.on('unselect', () => {
    if (cy.$(':selected').length === 0) setInspector(null);
  });

  return cy;
}

async function refreshBundles() {
  const data = await apiJson('/api/bundles');
  const sel = $("bundleSelect");
  sel.innerHTML = '';
  for (const p of data.bundles) {
    const opt = document.createElement('option');
    opt.value = p;
    opt.textContent = p;
    sel.appendChild(opt);
  }
  const has = data.bundles.length > 0;
  setEnabled($("btnVerify"), has);
  setEnabled($("btnReplay"), has);
  setEnabled($("btnEcologyImport"), has);
  setEnabled($("btnEcologyFull"), has);
}

async function refreshExports() {
  const data = await apiJson('/api/exports');
  const ul = $("exportsList");
  ul.innerHTML = '';
  for (const p of data.exports) {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.className = 'link';
    btn.textContent = p;
    btn.onclick = async () => {
      await navigator.clipboard.writeText(p);
      logLine(`Copied export path: ${p}`);
    };
    li.appendChild(btn);
    ul.appendChild(li);
  }
}

async function loadNodes() {
  const f = $("nodeFilter").value || '';
  const data = await apiJson(`/api/graph/nodes?filter=${encodeURIComponent(f)}&limit=400`);
  const sel = $("nodeSelect");
  sel.innerHTML = '';
  for (const n of data.nodes) {
    const opt = document.createElement('option');
    opt.value = n.id;
    opt.textContent = `${n.id}  [${n.type}]`;
    sel.appendChild(opt);
  }
  logLine(`Loaded ${data.nodes.length} nodes from ${data.db_path}`);
}

async function loadNeighborhood(nodeId) {
  const data = await apiJson(`/api/graph/neighborhood?node_id=${encodeURIComponent(nodeId)}&limit_edges=400`);

  const c = ensureCy();
  const centerId = data.center.id;

  const nodeEls = (data.nodes || []).map(n => ({
    data: {
      id: n.id,
      label: shortId(n.id),
      type: n.type,
      attrs: n.attrs ?? null,
      isCenter: n.id === centerId ? 1 : 0
    }
  }));

  const edgeEls = (data.edges || []).map(e => ({
    data: {
      id: `e:${e.id}`,
      source: e.src,
      target: e.dst,
      type: e.type || e.rel || '',
      attention_score: e.attention_score ?? null,
      attrs: e.attrs ?? null
    }
  }));

  c.elements().remove();
  c.add(nodeEls);
  c.add(edgeEls);

  c.layout({
    name: 'breadthfirst',
    roots: `#${CSS.escape(centerId)}`,
    directed: true,
    spacingFactor: 1.2,
    padding: 10
  }).run();

  c.fit(c.elements(), 20);
  logLine(`Neighborhood: nodes=${data.nodes.length} edges=${data.edges.length}`);
}

function wireTabs() {
  const tabs = document.querySelectorAll('.tab');
  tabs.forEach(t => {
    t.addEventListener('click', () => {
      tabs.forEach(x => x.classList.remove('active'));
      t.classList.add('active');

      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      $("panel-" + t.dataset.panel).classList.add('active');
    });
  });
}


function _activePanelId() {
  const active = document.querySelector('.panel.active');
  return active ? active.id : '';
}


function _parseCmdStdoutJson(res) {
  try {
    const s = (res && res.stdout ? String(res.stdout) : '').trim();
    if (!s) return null;
    return JSON.parse(s);
  } catch {
    return null;
  }
}


async function loadLLMStatus(silent=false) {
  const pre = $('llmStatusPre');
  const summary = $('llmSummary');
  const errEl = $('llmLastError');
  if (!pre || !summary || !errEl) return;

  try {
    const res = await apiJson('/api/termite/llm/status');
    const obj = _parseCmdStdoutJson(res);
    if (!obj) {
      pre.textContent = (res.stdout || '') + (res.stderr ? ('\n' + res.stderr) : '');
      summary.textContent = '(unparseable status)';
      errEl.textContent = '(unknown)';
      return;
    }
    pre.textContent = JSON.stringify(obj, null, 2);
    const running = !!obj.running;
    const provider = obj.provider || '';
    const model = obj.model || '';
    const baseUrl = obj.base_url || '';
    const endpointId = obj.endpoint_id || '';
    summary.textContent = `${running ? 'running' : 'stopped'}  provider=${provider}  model=${model}  base_url=${baseUrl}  endpoint_id=${endpointId}`;
    errEl.textContent = obj.last_error || '(none)';
  } catch (e) {
    if (!silent) {
      pre.textContent = String(e);
      summary.textContent = '(error)';
      errEl.textContent = e && e.message ? e.message : String(e);
      logLine('LLM status error: ' + (e && e.message ? e.message : String(e)));
    }
  }
}


function wireLLMUI() {
  const btnStart = $('btnLLMStart');
  const btnStop = $('btnLLMStop');
  const btnPing = $('btnLLMPing');
  const btnRefresh = $('btnLLMRefresh');

  if (btnStart) {
    btnStart.onclick = async () => {
      await withDisabled(btnStart, async () => {
        logLine('LLM start');
        const res = await apiJson('/api/termite/llm/start', { method: 'POST' });
        logCmdResult(res);
        await loadLLMStatus(true);
      });
    };
  }

  if (btnStop) {
    btnStop.onclick = async () => {
      await withDisabled(btnStop, async () => {
        logLine('LLM stop');
        const res = await apiJson('/api/termite/llm/stop', { method: 'POST' });
        logCmdResult(res);
        await loadLLMStatus(true);
      });
    };
  }

  if (btnPing) {
    btnPing.onclick = async () => {
      await withDisabled(btnPing, async () => {
        logLine('LLM ping');
        const res = await apiJson('/api/termite/llm/ping', { method: 'POST' });
        logCmdResult(res);
        await loadLLMStatus(true);
      });
    };
  }

  if (btnRefresh) {
    btnRefresh.onclick = async () => {
      await withDisabled(btnRefresh, async () => {
        await loadLLMStatus();
      });
    };
  }
}



function wireAuthUI() {
  const input = $('apiToken');
  const btnSet = $('btnSaveToken');
  const btnClear = $('btnClearToken');

  const render = () => {
    const tok = getApiToken();
    if (input) input.value = tok;
    if (!tok) {
      setAuthStatus('(no token)');
    } else {
      setAuthStatus(`token set (${tok.length} chars)`);
    }
  };

  if (btnSet) {
    btnSet.onclick = () => {
      setApiToken(input ? input.value : '');
      render();
      logLine('API token set (stored locally in this browser).');
      toast('Token stored locally in this browser.', { kind: 'info', timeoutMs: 2000 });
    };
  }

  if (btnClear) {
    btnClear.onclick = () => {
      setApiToken('');
      if (input) input.value = '';
      render();
      logLine('API token cleared.');
      toast('Token cleared.', { kind: 'info', timeoutMs: 2000 });
    };
  }

  render();
}
async function init() {
  wireTabs();
  wireAuthUI();
  wireLLMUI();

  // Catalog
  initCatalogView({ toast });

  // Jobs
  let selectedJobId = null;
  const refreshJobsUI = async (silent=false) => {
    try {
      const status = $("jobsStatus").value;
      const limit = parseInt($("jobsLimit").value || "50", 10);
      const data = await apiJobs(limit, status);
      const jobs = data.jobs || [];
      const rows = jobs.map(j => {
        const link = `<a data-jobid="${j.id}">#${j.id}</a>`;
        const created = fmtTs(j.created_at);
        const started = fmtTs(j.started_at);
        const finished = fmtTs(j.finished_at);
        return `<tr><td>${link}</td><td>${esc(j.kind)}</td><td>${esc(j.status)}</td><td>${created}</td><td>${started}</td><td>${finished}</td></tr>`;
      }).join("");
      $("jobsTableWrap").innerHTML = `<table class="jobsTable"><thead><tr><th>id</th><th>kind</th><th>status</th><th>created</th><th>started</th><th>finished</th></tr></thead><tbody>${rows || "<tr><td colspan=6>(none)</td></tr>"}</tbody></table>`;
      $("jobsTableWrap").querySelectorAll("a[data-jobid]").forEach(a => {
        a.onclick = async () => {
          selectedJobId = parseInt(a.dataset.jobid, 10);
          await loadJobDetail(selectedJobId);
        };
      });
      if (selectedJobId) {
        await loadJobDetail(selectedJobId, true);
      }
    } catch (e) {
      if (!silent) $("jobEnqueueOut").textContent = String(e);
    }
  };

  const loadJobDetail = async (jobId, silent=false) => {
    try {
      const j = (await apiJob(jobId)).job;
      $("jobDetail").textContent = JSON.stringify(j, null, 2);
      $("btnCancelJob").disabled = !(j.status === "queued");
      const logs = (await apiJobLogs(jobId, 2000)).logs || [];
      $("jobLogs").textContent = logs.map(x => `[${fmtTs(x.ts)}] ${x.level.toUpperCase()} ${x.message}`).join("\n");
    } catch (e) {
      if (!silent) $("jobDetail").textContent = String(e);
    }
  };

  $("btnUploadRun").onclick = async () => {
    await withDisabled($("btnUploadRun"), async () => {
      const label = $("jobLabel").value || "run";
      const f = $("jobFile").files[0];
      if (!f) throw new Error("Choose a file");
      const res = await apiUploadRun(label, f);
      $("jobEnqueueOut").textContent = JSON.stringify(res, null, 2);
      selectedJobId = res.job_id;
      await refreshJobsUI(true);
      await loadJobDetail(selectedJobId, true);
    });
  };

  $("btnRefreshJobs").onclick = async () => { await refreshJobsUI(); };
  $("jobsStatus").onchange = async () => { await refreshJobsUI(true); };
  $("jobsLimit").onchange = async () => { await refreshJobsUI(true); };
  $("btnCancelJob").onclick = async () => {
    if (!selectedJobId) return;
    const res = await apiCancelJob(selectedJobId);
    $("jobEnqueueOut").textContent = JSON.stringify(res, null, 2);
    await refreshJobsUI(true);
    await loadJobDetail(selectedJobId, true);
  };

  // Light polling (kept cheap; the backend stores logs in sqlite)
  setInterval(async () => {
    const pid = _activePanelId();
    const isJobs = pid === 'panel-jobs';
    if (isJobs || selectedJobId) {
      await refreshJobsUI(true);
    }
  }, 2000);

  // LLM polling only when the panel is visible.
  setInterval(async () => {
    const pid = _activePanelId();
    if (pid === 'panel-llm') {
      await loadLLMStatus(true);
    }
  }, 2000);


  let st = null;
  try {
    st = await apiJson('/api/state');
    $("policyPath").value = st.default_policy;
    $("allowlistPath").value = st.default_allowlist;
    renderStateBadges(st);
  } catch (e) {
    // Likely auth (401/403) or server not reachable; keep UI usable and let the user set a token.
    logLine('State fetch failed: ' + e.message);
    setAuthStatus('auth may be required — set API token and retry an action');
    renderStateBadges(null);
  }

  // Ingest
  $("btnUpload").onclick = async () => {
    await withDisabled($("btnUpload"), async () => {
      const f = $("uploadFile").files[0];
      if (!f) {
        logLine('No file selected');
        return;
      }
      const fd = new FormData();
      fd.append('file', f);
      logLine(`Uploading: ${f.name} (${f.size} bytes)`);
      const data = await apiJson('/api/ingest/upload', { method: 'POST', body: fd });
      $("savedUploadPath").textContent = data.saved_path;
      setEnabled($("btnIngest"), true);
      logLine(`Saved upload: ${data.saved_path}`);
    });
  };

  $("btnIngest").onclick = async () => {
    await withDisabled($("btnIngest"), async () => {
      const p = $("savedUploadPath").textContent;
      if (!p || p === '(none)') return;
      logLine(`Ingesting: ${p}`);
      const res = await apiJson('/api/termite/ingest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: p })
      });
      logCmdResult(res);
    });
  };

  $("btnSeal").onclick = async () => {
    await withDisabled($("btnSeal"), async () => {
      const label = $("sealLabel").value || 'demo';
      logLine(`Sealing bundle label=${label}`);
      const res = await apiJson('/api/termite/seal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ label })
      });
      logCmdResult(res);
      const p = (res.stdout || '').trim();
      if (p) {
        $("lastBundlePath").textContent = p;
        await refreshBundles();
      }
    });
  };

  // Bundles
  $("btnRefreshBundles").onclick = async () => {
    await withDisabled($("btnRefreshBundles"), async () => {
      logLine('Refreshing bundle list');
      await refreshBundles();
    });
  };

  $("btnVerify").onclick = async () => {
    await withDisabled($("btnVerify"), async () => {
      const bundle = selectedBundlePath();
      if (!bundle) return;
      logLine(`Verifying: ${bundle}`);
      const res = await apiJson('/api/termite/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bundle_path: bundle,
          policy: $("policyPath").value,
          allowlist: $("allowlistPath").value,
        })
      });
      logCmdResult(res);
    });
  };

  $("btnReplay").onclick = async () => {
    await withDisabled($("btnReplay"), async () => {
      const bundle = selectedBundlePath();
      if (!bundle) return;
      logLine(`Replaying: ${bundle}`);
      const res = await apiJson('/api/termite/replay', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bundle_path: bundle,
          policy: $("policyPath").value,
          allowlist: $("allowlistPath").value,
        })
      });
      logCmdResult(res);
    });
  };

  // Ecology
  $("btnEcologyInit").onclick = async () => {
    await withDisabled($("btnEcologyInit"), async () => {
      logLine('Ecology init');
      const res = await apiJson('/api/ecology/init', { method: 'POST' });
      logCmdResult(res);
    });
  };

  $("btnEcologyImport").onclick = async () => {
    await withDisabled($("btnEcologyImport"), async () => {
      const bundle = selectedBundlePath();
      if (!bundle) return;
      logLine(`Ecology import: ${bundle}`);
      const res = await apiJson('/api/ecology/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bundle_path: bundle })
      });
      logCmdResult(res);
    });
  };

  $("btnEcologyFull").onclick = async () => {
    await withDisabled($("btnEcologyFull"), async () => {
      const bundle = selectedBundlePath();
      if (!bundle) return;
      logLine(`Ecology full pipeline: ${bundle}`);
      const data = await apiJson('/api/ecology/full_pipeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ bundle_path: bundle })
      });
      for (const r of data.steps) {
        logCmdResult(r);
      }
      await refreshExports();
    });
  };

  $("btnReplayVerify").onclick = async () => {
    await withDisabled($("btnReplayVerify"), async () => {
      logLine('Ecology replay-verify');
      const res = await apiJson('/api/ecology/replay_verify', { method: 'POST' });
      logCmdResult(res);
    });
  };

  $("btnRefreshExports").onclick = async () => {
    await withDisabled($("btnRefreshExports"), async () => {
      logLine('Refreshing exports list');
      await refreshExports();
    });
  };



  // KG Validation + Review/Quarantine
  function parseStdoutJson(res) {
    try {
      const s = (res.stdout || '').trim();
      if (!s) return null;
      return JSON.parse(s);
    } catch {
      return null;
    }
  }

  async function runKgValidate() {
    const out = $('kgValidateOut');
    const btn = $('kgValidateBtn');
    if (!out || !btn) return;
    await withDisabled(btn, async () => {
      out.textContent = '';
      logLine('KG validate (SHACL-lite)');
      try {
        const res = await apiJson('/api/ecology/kg_validate');
        const obj = parseStdoutJson(res);
        out.textContent = obj ? JSON.stringify(obj, null, 2) : ((res.stdout || '') + (res.stderr ? ("\n" + res.stderr) : ''));
        logCmdResult(res);
      } catch (e) {
        out.textContent = String(e);
        logLine('KG validate error: ' + e.message);
      }
    });
  }

  async function fetchStaged(status) {
    const res = await apiJson('/api/ecology/review_list', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: status || null })
    });
    const obj = parseStdoutJson(res);
    const rows = (obj && obj.rows) ? obj.rows : null;
    return { res, rows };
  }

  function renderStagedList(rows) {
    const host = $('stagedList');
    if (!host) return;
    host.innerHTML = '';
    if (!rows || rows.length === 0) {
      host.textContent = '(none)';
      return;
    }

    for (const r of rows) {
      const card = document.createElement('div');
      card.className = 'card';

      const header = document.createElement('div');
      header.className = 'row';
      const title = document.createElement('div');
      title.className = 'mono';
      title.textContent = `#${r.id}  status=${r.status}  ts=${r.ts_utc}`;
      header.appendChild(title);
      card.appendChild(header);

      const meta = document.createElement('div');
      meta.className = 'mono small';
      meta.textContent = `bundle=${r.bundle_name}  ops=${r.ops_count}  delta=${(r.kg_delta_hash || '').slice(0, 12)}…`;
      card.appendChild(meta);

      const v = document.createElement('div');
      v.className = 'mono small';
      const ok = r.verified_ok ? 'ok' : 'FAILED';
      const reason = (r.verify_reason || '').toString();
      v.textContent = `verify=${ok}${reason ? '  reason=' + reason : ''}`;
      card.appendChild(v);

      const reportsWrap = document.createElement('div');
      reportsWrap.className = 'row';

      const details = document.createElement('details');
      details.style.marginTop = '6px';
      const sum = document.createElement('summary');
      sum.textContent = 'Reports (contracts / KG validation)';
      details.appendChild(sum);
      const pre = document.createElement('pre');
      pre.className = 'mono small pre';
      const repObj = {
        contracts_report_json: r.contracts_report_json ? safeJson(r.contracts_report_json) : null,
        kg_shacl_report_json: r.kg_shacl_report_json ? safeJson(r.kg_shacl_report_json) : null,
        decision_ts_utc: r.decision_ts_utc || null,
        decision_actor: r.decision_actor || null,
        decision_notes: r.decision_notes || null,
      };
      pre.textContent = JSON.stringify(repObj, null, 2);
      details.appendChild(pre);
      card.appendChild(details);

      const actions = document.createElement('div');
      actions.className = 'row';
      actions.style.marginTop = '8px';

      const notes = document.createElement('input');
      notes.type = 'text';
      notes.placeholder = 'notes (optional)';
      notes.style.flex = '1';
      actions.appendChild(notes);

      const canDecide = (r.status === 'PENDING' || r.status === 'QUARANTINED');

      const btnApprove = document.createElement('button');
      btnApprove.textContent = 'Approve';
      btnApprove.disabled = !canDecide;
      btnApprove.onclick = async () => {
        await withDisabled(btnApprove, async () => {
          logLine(`Approve staged #${r.id}`);
          const res = await apiJson('/api/ecology/review_approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: r.id, actor: 'ui', notes: notes.value || '' })
          });
          logCmdResult(res);
          await refreshStagedUI(true);
          await runKgValidate();
        });
      };
      actions.appendChild(btnApprove);

      const btnReject = document.createElement('button');
      btnReject.textContent = 'Reject';
      btnReject.className = 'danger';
      btnReject.disabled = !canDecide;
      btnReject.onclick = async () => {
        if (!confirm(`Reject staged bundle #${r.id}?`)) return;
        await withDisabled(btnReject, async () => {
          logLine(`Reject staged #${r.id}`);
          const res = await apiJson('/api/ecology/review_reject', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: r.id, actor: 'ui', notes: notes.value || '' })
          });
          logCmdResult(res);
          await refreshStagedUI(true);
        });
      };
      actions.appendChild(btnReject);

      card.appendChild(actions);
      host.appendChild(card);
    }
  }

  function safeJson(s) {
    try { return JSON.parse(String(s)); } catch { return String(s); }
  }

  async function refreshStagedUI(silent=false) {
    const btn = $('stagedRefreshBtn');
    const out = $('stagedList');
    if (!btn || !out) return;

    const statusSel = $('stagedStatusSel');
    const status = statusSel ? (statusSel.value || null) : null;

    const runner = async () => {
      try {
        out.textContent = '';
        const { res, rows } = await fetchStaged(status);
        if (!rows) {
          // Fallback: show raw output
          out.textContent = (res.stdout || '').trim() || '(none)';
          if (res.stderr && res.stderr.trim()) out.textContent += "\n" + res.stderr.trim();
        } else {
          renderStagedList(rows);
        }
      } catch (e) {
        if (!silent) out.textContent = String(e);
        logLine('Staged refresh error: ' + e.message);
      }
    };

    if (btn) {
      await withDisabled(btn, runner);
    } else {
      await runner();
    }
  }

  const kgBtn = $('kgValidateBtn');
  if (kgBtn) kgBtn.onclick = async () => { await runKgValidate(); };

  const stgBtn = $('stagedRefreshBtn');
  if (stgBtn) stgBtn.onclick = async () => { await refreshStagedUI(); };

  const stSel = $('stagedStatusSel');
  if (stSel) stSel.onchange = async () => { await refreshStagedUI(true); };

  // GraphDelta ledger
  const btnRefreshRuns = $('btnRefreshRuns');
  const btnLoadDeltas = $('btnLoadDeltas');
  const runSel = $('runSelect');

  if (btnRefreshRuns) {
    btnRefreshRuns.onclick = async () => {
      await withDisabled(btnRefreshRuns, async () => {
        await refreshRunsUI();
      });
    };
  }

  if (btnLoadDeltas) {
    btnLoadDeltas.onclick = async () => {
      await withDisabled(btnLoadDeltas, async () => {
        _renderRunContext(_selectedRunId());
        await loadDeltasUI();
      });
    };
  }

  if (runSel) {
    runSel.onchange = async () => {
      _renderRunContext(_selectedRunId());
      if (btnLoadDeltas) {
        await withDisabled(btnLoadDeltas, async () => {
          await loadDeltasUI();
        });
      } else {
        await loadDeltasUI();
      }
    };
  }

  // Graph
  $("btnLoadNodes").onclick = async () => {
    await withDisabled($("btnLoadNodes"), async () => {
      await loadNodes();
    });
  };

  $("nodeSelect").onchange = async () => {
    await withDisabled($("nodeSelect"), async () => {
      const id = $("nodeSelect").value;
      if (!id) return;
      await loadNeighborhood(id);
    });
  };

  // Initial loads
  await refreshBundles();
  await refreshExports();

  // Best-effort: populate run selector for filtering deltas.
  try {
    await refreshRunsUI();
    await loadDeltasUI();
  } catch (e) {
    // Ignore (e.g., auth); user can retry via Refresh.
  }
}

window.addEventListener('DOMContentLoaded', () => {
  init().catch(err => {
    logLine(`Init error: ${err.message}`);
  });
});
