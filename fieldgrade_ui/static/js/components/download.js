export function downloadText(filename, text, mime = 'text/plain') {
  const blob = new Blob([text || ''], { type: mime });
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'download.txt';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 500);
  }
}
