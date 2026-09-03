// Рисует favicon.ico и og.jpg в языке самой страницы.
//
//   node oformlenie.mjs        (нужен Chromium; шрифт берётся из site/fonts)
//
// Зачем отдельный скрипт. Иконку и картинку превью не проверяет ни один из
// наших скриптов — в CLAUDE.md так и записано, «их смотрят глазами», — и
// именно они утекли из шаблона Lovable на боевой прототип: в закладках у
// владельца висел розовый значок конструктора. Теперь они рисуются свои.
//
// Почему не берём логотип клиента: у них в шапке синяя снежинка с надписью
// Kondi-Kaluga.ru, то есть штамп ниши, который мы вычищали со всей страницы.

import { chromium } from '/opt/node22/lib/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const KOREN = path.dirname(fileURLToPath(import.meta.url));
const SAYT = path.join(KOREN, 'site');
const SHRIFT = 'file://' + path.join(SAYT, 'fonts', 'manrope-cyrillic.woff2');
const SHRIFT_LAT = 'file://' + path.join(SAYT, 'fonts', 'manrope-latin.woff2');

const SHAPKA = `<style>
@font-face{font-family:Manrope;src:url('${SHRIFT}') format('woff2');font-weight:400 800;}
@font-face{font-family:Manrope;src:url('${SHRIFT_LAT}') format('woff2');font-weight:400 800;}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Manrope,system-ui,sans-serif;-webkit-font-smoothing:antialiased}
</style>`;

// Иконка: тёмный квадрат и голубая «К». На 16 px читается только буква —
// шкала, градиент и любой значок в этом размере превращаются в кашу.
const IKONKA = (r) => `${SHAPKA}<div style="
  width:${r}px;height:${r}px;background:#111319;border-radius:${Math.round(r * 0.22)}px;
  display:flex;align-items:center;justify-content:center;
  color:#38bdf8;font-weight:800;font-size:${Math.round(r * 0.68)}px;
  letter-spacing:-0.04em;line-height:1;padding-bottom:${Math.round(r * 0.04)}px;
">К</div>`;

// Превью для мессенджеров: фото фасада из выгрузки читалось как облезлый дом
// без единого слова. Ссылку пересылают — на ней должно быть видно, кто и почём.
const PREVIU = `${SHAPKA}<div style="
  width:1200px;height:630px;background:#111319;position:relative;overflow:hidden;
  padding:80px;display:flex;flex-direction:column;justify-content:space-between;">
  <div style="position:absolute;top:-160px;right:-120px;width:620px;height:620px;
       background:radial-gradient(circle,rgba(56,189,248,0.22),transparent 62%)"></div>
  <div style="position:absolute;bottom:-200px;left:-140px;width:520px;height:520px;
       background:radial-gradient(circle,rgba(56,189,248,0.10),transparent 65%)"></div>
  <div style="position:relative;display:flex;align-items:center;gap:16px">
    <div style="width:44px;height:44px;background:#0b0e13;border-radius:10px;
         border:1px solid rgba(255,255,255,0.08);display:flex;align-items:center;
         justify-content:center;color:#38bdf8;font-weight:800;font-size:26px">К</div>
    <span style="color:#87929a;font-weight:700;font-size:15px;letter-spacing:0.12em">
      КОНДИ-КАЛУГА · КАЛУГА, С 2004 ГОДА</span>
  </div>
  <div style="position:relative">
    <div style="color:#e1e2ea;font-weight:800;font-size:74px;line-height:1.05;
         letter-spacing:-0.03em;max-width:900px">Монтаж кондиционеров<br/>в Калуге</div>
    <div style="color:#bdc8d1;font-size:26px;margin-top:26px">
      Цену называем до выезда и не меняем на объекте</div>
  </div>
  <div style="position:relative;display:flex;align-items:flex-end;gap:56px">
    ${[['Стандартный монтаж «девятки»', '12 000 ₽'],
       ['Трасса в цене', '5 метров'],
       ['Гарантия на монтаж', '1 год']].map(([p, z]) => `
    <div>
      <div style="color:#87929a;font-size:15px;font-weight:700;letter-spacing:0.1em;
           text-transform:uppercase">${p}</div>
      <div style="color:#38bdf8;font-weight:800;font-size:38px;margin-top:8px">${z}</div>
    </div>`).join('')}
  </div>
</div>`;

const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });

// favicon.ico из двух размеров: 32 для вкладки, 64 для закладок и панели задач
const kadry = [];
for (const r of [32, 64]) {
  const p = await b.newPage({ viewport: { width: r, height: r }, deviceScaleFactor: 1 });
  await p.setContent(IKONKA(r));
  await p.evaluate(() => document.fonts.ready);
  kadry.push({ r, png: await p.screenshot({ omitBackground: false }) });
  await p.close();
}

// Контейнер ICO с PNG внутри: так умеют все браузеры со времён Vista, и это
// избавляет от возни с BMP и маской прозрачности.
const zagolovok = Buffer.alloc(6 + 16 * kadry.length);
zagolovok.writeUInt16LE(0, 0); zagolovok.writeUInt16LE(1, 2);
zagolovok.writeUInt16LE(kadry.length, 4);
let smeshchenie = zagolovok.length;
kadry.forEach((k, i) => {
  const o = 6 + 16 * i;
  zagolovok.writeUInt8(k.r === 256 ? 0 : k.r, o);
  zagolovok.writeUInt8(k.r === 256 ? 0 : k.r, o + 1);
  zagolovok.writeUInt8(0, o + 2); zagolovok.writeUInt8(0, o + 3);
  zagolovok.writeUInt16LE(1, o + 4); zagolovok.writeUInt16LE(32, o + 6);
  zagolovok.writeUInt32LE(k.png.length, o + 8);
  zagolovok.writeUInt32LE(smeshchenie, o + 12);
  smeshchenie += k.png.length;
});
fs.writeFileSync(path.join(SAYT, 'favicon.ico'),
                 Buffer.concat([zagolovok, ...kadry.map((k) => k.png)]));

// og.jpg
const p = await b.newPage({ viewport: { width: 1200, height: 630 }, deviceScaleFactor: 1 });
await p.setContent(PREVIU);
await p.evaluate(() => document.fonts.ready);
await p.waitForTimeout(300);
await p.screenshot({ path: path.join(SAYT, 'og.jpg'), type: 'jpeg', quality: 88 });
await p.close();

await b.close();
console.log('favicon.ico:', (fs.statSync(path.join(SAYT, 'favicon.ico')).size / 1024).toFixed(1), 'КБ',
            '| og.jpg:', (fs.statSync(path.join(SAYT, 'og.jpg')).size / 1024).toFixed(1), 'КБ');
