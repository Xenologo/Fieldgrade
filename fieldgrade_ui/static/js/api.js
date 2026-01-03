import { getApiToken } from './state.js';

function _applyTokenHeader(options) {
  const tok = getApiToken();
  const opts = options ? { ...options } : {};
  const headers = new Headers(opts.headers || {});
  if (tok) headers.set('X-API-Key', tok);
  opts.headers = headers;
  return opts;
}

export async function apiFetch(path, options) {
  return await fetch(path, _applyTokenHeader(options));
}

export async function apiJson(path, options, hooks) {
  const res = await apiFetch(path, options);
  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    data = { ok: false, raw: text };
  }
  if (!res.ok) {
    if ((res.status === 401 || res.status === 403) && hooks && typeof hooks.onAuthError === 'function') {
      try {
        hooks.onAuthError({ res, data, text });
      } catch {
        // best-effort hook
      }
    }
    const detail = data && data.detail ? JSON.stringify(data.detail) : text;
    const err = new Error(`${res.status} ${res.statusText}: ${detail}`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return data;
}

export async function apiUploadRun(label, file) {
  const fd = new FormData();
  fd.append('label', label);
  fd.append('file', file);
  const r = await apiFetch('/api/pipeline/upload_run?label=' + encodeURIComponent(label), {
    method: 'POST',
    body: fd,
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error('upload_run failed: ' + t);
  }
  return await r.json();
}

export async function apiJobs(limit, status) {
  const qs = new URLSearchParams();
  qs.set('limit', String(limit ?? 50));
  if (status) qs.set('status', status);
  return await apiJson('/api/jobs?' + qs.toString());
}

export async function apiJob(jobId) {
  return await apiJson('/api/jobs/' + jobId);
}

export async function apiJobLogs(jobId, limit = 500) {
  return await apiJson('/api/jobs/' + jobId + '/logs?limit=' + limit);
}

export async function apiCancelJob(jobId) {
  return await apiJson('/api/jobs/' + jobId + '/cancel', { method: 'POST' });
}

export async function apiState() {
  return await apiJson('/api/state');
}

export async function apiBundles() {
  return await apiJson('/api/bundles');
}

export async function apiExports() {
  return await apiJson('/api/exports');
}

export async function apiRegistryComponents() {
  return await apiJson('/api/registry/components');
}

export async function apiRegistryVariants() {
  return await apiJson('/api/registry/variants');
}

export async function apiRegistryRemotes() {
  return await apiJson('/api/registry/remotes');
}
