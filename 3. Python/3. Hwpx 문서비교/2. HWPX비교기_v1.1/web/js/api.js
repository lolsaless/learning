// 파이썬 서버(hwpxdiff/server/routes.py)와 통신. 새 API 를 만들면 여기에 한 줄 추가한다.
async function call(method, url, body) {
  const opt = { method, headers: {} };
  if (body !== undefined) {
    opt.headers['Content-Type'] = 'application/json';
    opt.body = JSON.stringify(body);
  }
  const res = await fetch(url, opt);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `요청 실패 (${res.status})`);
  return data;
}

export const api = {
  info: () => call('GET', '/api/info'),
  status: since => call('GET', `/api/status?since=${since || 0}`),
  document: id => call('GET', `/api/document?id=${encodeURIComponent(id)}`),

  /** 파일 1개 올리기 (내용을 그대로 보냄, 이름은 머리글로) */
  async upload(file, relPath) {
    const res = await fetch('/api/upload', {
      method: 'POST',
      headers: { 'X-File-Name': encodeURIComponent(file.name), 'X-Rel-Path': encodeURIComponent(relPath || file.name),
                 'Content-Type': 'application/octet-stream' },
      body: file,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `올리기 실패 (${res.status})`);
    return data;
  },
  folder: (path, recursive) => call('POST', '/api/folder', { path, recursive }),
  remove: id => call('POST', '/api/remove', { id }),
  reset: () => call('POST', '/api/reset', {}),
  orderBy: mode => call('POST', '/api/order', { mode }),
  orderIds: ids => call('POST', '/api/order', { ids }),
  setOptions: options => call('POST', '/api/options', { options }),
  compare: (a, b) => call('POST', '/api/compare', { a, b }),
  history: () => call('POST', '/api/history', {}),
  render: (a, b, view) => call('POST', '/api/render', { a, b, view }),     // (v1.1) 문서 모양 보기
  shutdown: () => call('POST', '/api/shutdown', {}),
  exportUrl: (kind, fmt, a, b) =>
    `/api/export?kind=${kind}&fmt=${fmt}&a=${encodeURIComponent(a || '')}&b=${encodeURIComponent(b || '')}`,
};
