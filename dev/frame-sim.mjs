// Имитация рамки для проверки этапа 2 на тестовом HA: подключается как рамка, печатает всё, что ей приходит,
// и параллельно (вторым подключением, как пользователь HA) дёргает сущности и службы.
//   node dev/frame-sim.mjs
import { readFileSync } from 'node:fs';

const BASE = process.env.HA || 'http://localhost:8125';
const user = Object.fromEntries(readFileSync(new URL('./.test-user', import.meta.url), 'utf8').trim().split('\n').map((l) => l.split('=')));
const token = await fetch(BASE + '/auth/token', {
  method: 'POST',
  body: new URLSearchParams({ grant_type: 'refresh_token', refresh_token: user.refresh_token, client_id: BASE + '/' }),
}).then((r) => r.json()).then((d) => d.access_token);

function connect() {
  return new Promise((resolve) => {
    const ws = new WebSocket(BASE.replace(/^http/, 'ws') + '/api/websocket');
    let id = 0;
    const waiting = new Map();
    const events = new Map();
    ws.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.type === 'auth_required') ws.send(JSON.stringify({ type: 'auth', access_token: token }));
      else if (m.type === 'auth_ok') resolve(api);
      else if (m.type === 'result' && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); }
      else if (m.type === 'event' && events.has(m.id)) events.get(m.id)(m.event);
    };
    const api = {
      call: (msg) => new Promise((res) => { const mid = ++id; waiting.set(mid, res); ws.send(JSON.stringify({ id: mid, ...msg })); }),
      sub: (msg, onEvent) => { const mid = ++id; events.set(mid, onEvent); waiting.set(mid, () => {}); ws.send(JSON.stringify({ id: mid, ...msg })); },
      close: () => ws.close(),
    };
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const frame = await connect();
const FRAME = 'simframe0001';
frame.sub({ type: 'photoframe/frame/connect', frame_id: FRAME, name: 'Кухня', model: 'Android (APK)', version: '0.3.1' },
  (ev) => console.log('рамке пришло:', JSON.stringify(ev)));
await sleep(1500);
await frame.call({ type: 'photoframe/frame/report', frame_id: FRAME, photo: 'test-photo.jpg', photo_url: '/media/media/photoframe/test-photo.jpg' });

const ha = await connect();
const states = (await ha.call({ type: 'get_states' })).result.filter((s) => s.entity_id.includes('kukhnia') || s.entity_id.includes('kukhnya') || (s.attributes.friendly_name || '').startsWith('Кухня'));
for (const s of states) console.log('сущность:', s.entity_id, '=', s.state, s.attributes.options ? JSON.stringify(s.attributes.options) : '');
const album = states.find((s) => s.entity_id.startsWith('select.') && s.attributes.options && s.attributes.options.includes('all'));
const next = states.find((s) => s.entity_id.startsWith('button.') && /next|следующ/i.test(s.entity_id + s.attributes.friendly_name));
if (album) await ha.call({ type: 'call_service', domain: 'select', service: 'select_option', target: { entity_id: album.entity_id }, service_data: { option: 'Дача' } });
if (next) await ha.call({ type: 'call_service', domain: 'button', service: 'press', target: { entity_id: next.entity_id } });
await ha.call({ type: 'call_service', domain: 'photoframe', service: 'show_camera', service_data: { camera: 'camera.demo', duration: 15 } });
await sleep(1500);
frame.close();
await sleep(1500);
const online = (await ha.call({ type: 'get_states' })).result.find((s) => s.entity_id.startsWith('binary_sensor.') && (s.attributes.friendly_name || '').startsWith('Кухня'));
console.log('после отключения:', online && online.entity_id, '=', online && online.state);
ha.close();
