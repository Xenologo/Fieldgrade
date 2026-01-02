const FG_API_TOKEN_STORAGE_KEY = 'fieldgrade_ui_api_token_v1';

export function getApiToken() {
  try { return (localStorage.getItem(FG_API_TOKEN_STORAGE_KEY) || '').trim(); } catch { return ''; }
}

export function setApiToken(tok) {
  const t = (tok || '').toString().trim();
  try {
    if (t) localStorage.setItem(FG_API_TOKEN_STORAGE_KEY, t);
    else localStorage.removeItem(FG_API_TOKEN_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function createStore(initial) {
  let state = { ...(initial || {}) };
  const listeners = new Set();

  function getState() { return state; }

  function setState(patch) {
    state = { ...state, ...(patch || {}) };
    for (const fn of listeners) {
      try { fn(state); } catch { /* ignore */ }
    }
  }

  function subscribe(fn) {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }

  return { getState, setState, subscribe };
}
