let _root = null;

function ensureRoot() {
  if (_root) return _root;
  const el = document.createElement('div');
  el.id = 'toastRoot';
  el.className = 'toastRoot';
  el.setAttribute('aria-live', 'polite');
  el.setAttribute('aria-atomic', 'true');
  document.body.appendChild(el);
  _root = el;
  return el;
}

export function toast(message, { kind = 'info', timeoutMs = 5000 } = {}) {
  const root = ensureRoot();
  const item = document.createElement('div');
  item.className = `toast toast-${kind}`;
  item.tabIndex = 0;

  const msg = document.createElement('div');
  msg.className = 'toastMsg';
  msg.textContent = message || '';

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'toastClose';
  btn.textContent = 'Dismiss';
  btn.addEventListener('click', () => item.remove());

  item.appendChild(msg);
  item.appendChild(btn);
  root.appendChild(item);

  // Focus new errors to make keyboard-only workflows usable.
  if (kind === 'error') {
    try { item.focus(); } catch { /* ignore */ }
  }

  if (timeoutMs > 0) {
    setTimeout(() => {
      try { item.remove(); } catch { /* ignore */ }
    }, timeoutMs);
  }
}
