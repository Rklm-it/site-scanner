#!/usr/bin/env node
// Мост между Клодом (stdio) и MCP-сервером Stitch (HTTP).
//
// Напрямую сервер не подключается: в схеме инструмента upload_design_md
// объявлена ссылка #/$defs/ScreenInstance, а само определение не приходит.
// Клод на неразрешимой ссылке отбрасывает ВЕСЬ список инструментов — то есть
// из-за одного сломанного все пятнадцать становятся недоступны. Это баг на
// стороне Google; чинить у себя дешевле, чем ждать.
//
// Мост делает три вещи и больше ничего: перекладывает JSON-RPC со stdin в
// POST и обратно, тащит за собой Mcp-Session-Id, и на ответе tools/list
// дописывает недостающие определения как свободный объект. Подменять смысл
// схемы нельзя — только закрыть дыру, чтобы валидатор пропустил список.
const URL_MCP = process.env.STITCH_MCP_URL || 'https://stitch.googleapis.com/mcp';
const KEY = process.env.STITCH_API_KEY || '';

if (!KEY) {
  process.stderr.write('STITCH_API_KEY не задан: экспортируй ключ в окружение\n');
}

let session = null;

// Ссылки чинятся рекурсивно: $ref встречается и внутри properties, и в items.
function sobratRefs(node, acc) {
  if (Array.isArray(node)) { for (const v of node) sobratRefs(v, acc); return acc; }
  if (node && typeof node === 'object') {
    for (const [k, v] of Object.entries(node)) {
      if (k === '$ref' && typeof v === 'string' && v.startsWith('#/$defs/')) acc.add(v.slice(8));
      else sobratRefs(v, acc);
    }
  }
  return acc;
}

function pochinit(shema) {
  if (!shema || typeof shema !== 'object') return;
  const nuzhno = sobratRefs(shema, new Set());
  const est = new Set(Object.keys(shema.$defs || {}));
  const net = [...nuzhno].filter((n) => !est.has(n));
  if (!net.length) return;
  shema.$defs = shema.$defs || {};
  // Свободный объект: не врём про поля, которых не знаем, но ссылка становится
  // разрешимой и список инструментов проходит проверку целиком.
  for (const imya of net) shema.$defs[imya] = { type: 'object' };
}

// Ответ клиенту об ошибке, а не молчание. Молчание клиент трактует как «сервер
// не отвечает» и ждёт свой таймаут: без ключа Stitch отдаёт на initialize
// HTML-страницу 401, мост её не разбирал, и сессия объявляла сервер мёртвым
// через 30 секунд вместо внятного «нет ключа».
function oshibka(soobshenie, tekst) {
  if (!soobshenie || soobshenie.id === undefined) return null;   // уведомление
  return { jsonrpc: '2.0', id: soobshenie.id, error: { code: -32000, message: tekst } };
}

async function otpravit(soobshenie) {
  const zagolovki = {
    'Content-Type': 'application/json',
    Accept: 'application/json, text/event-stream',
    'X-Goog-Api-Key': KEY,
  };
  if (session) zagolovki['Mcp-Session-Id'] = session;

  const otvet = await fetch(URL_MCP, {
    method: 'POST', headers: zagolovki, body: JSON.stringify(soobshenie),
  });
  const sid = otvet.headers.get('mcp-session-id');
  if (sid) session = sid;

  const telo = await otvet.text();
  if (!telo.trim()) return null;

  if (!otvet.ok) {
    const chego = otvet.status === 401 || otvet.status === 403
      ? 'нет ключа STITCH_API_KEY в окружении сессии или он недействителен'
      : telo.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 160);
    return oshibka(soobshenie, `Stitch ответил ${otvet.status}: ${chego}`);
  }

  // Сервер вправе ответить потоком SSE вместо json — тогда полезное лежит в data:
  const tip = otvet.headers.get('content-type') || '';
  const syroe = tip.includes('text/event-stream')
    ? telo.split('\n').filter((s) => s.startsWith('data:')).map((s) => s.slice(5).trim()).join('')
    : telo;

  try { return JSON.parse(syroe); } catch {
    process.stderr.write(`не разобрал ответ (${otvet.status}): ${telo.slice(0, 200)}\n`);
    return oshibka(soobshenie, `Stitch вернул не JSON (${otvet.status})`);
  }
}

let bufer = '';
const ochered = [];        // разобранные сообщения ждут своей очереди
let idet = false;          // насос уже крутится
let vhodZakryt = false;

// Выходить по закрытию stdin сразу нельзя: при пайпе он закрывается раньше,
// чем придут ответы, и они теряются. И считать «в полёте» по одному запросу
// тоже мало — пока ждём ответ на первый, остальные строки уже разобраны и
// лежат в очереди. Выход только когда вход закрыт и очередь пуста.
// Писать без подтверждения нельзя: tools/list у Stitch больше 64 КБ, это
// перестаёт помещаться в буфер трубы за один раз. Без ожидания записи выход
// обрубал ответ на середине, и клиент получал битый JSON.
function pisat(stroka) {
  return new Promise((gotovo) => process.stdout.write(stroka, gotovo));
}

function mozhnoVyhodit() {
  if (vhodZakryt && !idet && ochered.length === 0) process.exit(0);
}

async function nasos() {
  if (idet) return;
  idet = true;
  while (ochered.length) {
    const soobshenie = ochered.shift();
    try {
      const otvet = await otpravit(soobshenie);
      if (otvet) {
        if (otvet.result && Array.isArray(otvet.result.tools)) {
          for (const t of otvet.result.tools) { pochinit(t.inputSchema); pochinit(t.outputSchema); }
        }
        await pisat(JSON.stringify(otvet) + '\n');
      }
    } catch (e) {
      process.stderr.write(`сбой запроса: ${e && e.message}\n`);
      const o = oshibka(soobshenie, `не достучался до Stitch: ${e && e.message}`);
      if (o) await pisat(JSON.stringify(o) + '\n');
    }
  }
  idet = false;
  mozhnoVyhodit();
}

process.stdin.setEncoding('utf8');
process.stdin.on('data', (kusok) => {
  bufer += kusok;
  let i;
  while ((i = bufer.indexOf('\n')) >= 0) {
    const stroka = bufer.slice(0, i).trim();
    bufer = bufer.slice(i + 1);
    if (!stroka) continue;
    try { ochered.push(JSON.parse(stroka)); } catch { continue; }
  }
  nasos();
});
process.stdin.on('end', () => { vhodZakryt = true; mozhnoVyhodit(); });
