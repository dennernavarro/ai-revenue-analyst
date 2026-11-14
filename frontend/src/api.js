async function request(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `${res.status} ${res.statusText}`);
  }
  return res.json();
}

const get = (path) => request(path);
const post = (path, body) =>
  request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

export const api = {
  properties: () => get('/properties'),
  performance: (id, start, end) =>
    get(`/properties/${id}/performance?start=${start}&end=${end}`),
  calendar: (id, start, end) => get(`/properties/${id}/calendar?start=${start}&end=${end}`),
  roomTypes: (id, start, end) =>
    get(`/properties/${id}/room-types?start=${start}&end=${end}`),
  chat: (message, conversationId) =>
    post('/chat', { message, conversation_id: conversationId }),
  startReview: (propertyId, start, end) =>
    post('/reviews', { property_id: propertyId, start, end }),
  decideReview: (reviewId, approved, note = '') =>
    post(`/reviews/${reviewId}/decision`, { approved, note }),
};

export const iso = (d) => d.toISOString().slice(0, 10);

export function monthRange(year, month) {
  const start = new Date(Date.UTC(year, month, 1));
  const end = new Date(Date.UTC(year, month + 1, 1));
  return { start: iso(start), end: iso(end) };
}
