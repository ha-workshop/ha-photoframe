// Запросы к WebSocket API тестового HA от имени тестового пользователя (dev/.test-user):
//   node dev/ws.mjs '[{"type":"photoframe/config"}]'
// Печатает ответ на каждый запрос; для подписок — ещё первое событие.
import { readFileSync } from 'node:fs';

const BASE = process.env.HA || 'http://localhost:8125';
const user = Object.fromEntries(readFileSync(new URL('./.test-user', import.meta.url), 'utf8').trim().split('\n').map((l) => l.split('=')));
const token = await fetch(BASE + '/auth/token', {
  method: 'POST',
  body: new URLSearchParams({ grant_type: 'refresh_token', refresh_token: user.refresh_token, client_id: BASE + '/' }),
}).then((r) => r.json()).then((d) => d.access_token);

const messages = JSON.parse(process.argv[2] || '[]');
const ws = new WebSocket(BASE.replace(/^http/, 'ws') + '/api/websocket');
let id = 0;
const waiting = new Map();
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.type === 'auth_required') ws.send(JSON.stringify({ type: 'auth', access_token: token }));
  else if (m.type === 'auth_ok') next();
  else if (m.type === 'auth_invalid') { console.error('auth_invalid'); process.exit(1); }
  else if (waiting.has(m.id)) {
    const w = waiting.get(m.id);
    if (m.type === 'result') {
      console.log(JSON.stringify({ request: w.msg.type, success: m.success, result: m.result, error: m.error }));
      if (!w.subscribe || !m.success) { waiting.delete(m.id); next(); }
    } else if (m.type === 'event') {
      console.log(JSON.stringify({ event: w.msg.type, data: m.event }));
      waiting.delete(m.id);
      next();
    }
  }
};
function next() {
  const msg = messages.shift();
  if (!msg) { ws.close(); return; }
  const mid = ++id;
  waiting.set(mid, { msg, subscribe: /subscribe/.test(msg.type) });
  ws.send(JSON.stringify({ id: mid, ...msg }));
}
