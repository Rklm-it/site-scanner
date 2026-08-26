# Приёмы по блокам: готовые куски

Порядок в каждом пункте один: сначала на голом CSS (ноль килобайт), рядом —
тот же приём на `motion`, если проект на React и библиотека уже стоит. Брать
отсюда, а не сочинять заново: тут уже учтены `prefers-reduced-motion`,
мобильный и то, что анимируются только `transform` и `opacity`.

## Токены: длительность и кривая в одном месте

```css
:root {
  --dur-ui: .18s;         /* отклик интерфейса */
  --dur-reveal: .4s;      /* появление блока */
  --ease: cubic-bezier(.16, 1, .3, 1);   /* быстро стартует, мягко тормозит */
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Значения в переменных, а не в каждом правиле: клиент скажет «слишком
резво» — правится одна строка, а не сорок.

## 1. Появление секции при прокрутке

Ноль килобайт, работает в любом проекте:

```css
.reveal { opacity: 0; transform: translateY(16px);
          transition: opacity var(--dur-reveal) var(--ease),
                      transform var(--dur-reveal) var(--ease); }
.reveal.is-in { opacity: 1; transform: none; }
```

```js
// once: элемент, который уже показался, обратно не прячем — от этого рябит
const io = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) {
    e.target.classList.add('is-in');
    io.unobserve(e.target);
  }
}, { rootMargin: '0px 0px -10% 0px' });
document.querySelectorAll('.reveal').forEach((el) => io.observe(el));
```

Важное: если JS не выполнится, `.reveal` останется невидимым. Поэтому класс
вешать скриптом на этапе загрузки (`document.documentElement.classList.add('js')`
и правило `.js .reveal { opacity: 0 }`), а на первом экране — не вешать вовсе.

На `motion` то же самое:

```jsx
<motion.section
  initial={{ opacity: 0, y: 16 }}
  whileInView={{ opacity: 1, y: 0 }}
  viewport={{ once: true, margin: '0px 0px -10% 0px' }}
  transition={{ duration: .4, ease: [.16, 1, .3, 1] }}
/>
```

## 2. Карточки лесенкой

```css
.card { transition-delay: calc(var(--i) * 60ms); }  /* style="--i:0|1|2..." */
```

Не больше пяти шагов: шестая карточка ждёт треть секунды после первой, и это
уже заметно как задержка, а не как приём. Дальше — все разом.

На `motion` — `staggerChildren` у родителя:

```jsx
const list = { animate: { transition: { staggerChildren: .06 } } };
const item = { initial: { opacity: 0, y: 12 }, animate: { opacity: 1, y: 0 } };
```

## 3. Кнопки, ссылки, поля

```css
.btn { transition: transform var(--dur-ui) var(--ease),
                   background-color var(--dur-ui) var(--ease); }
.btn:hover  { transform: translateY(-1px); }
.btn:active { transform: translateY(0); }
.btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```

На телефоне `hover` не существует, а `:active` срабатывает с задержкой. Всё,
что важно (цена, наличие, телефон), должно быть видно **без** наведения:
раскрытие по hover на мобильном просто не случится.

`:focus-visible` не убирать — им пользуются с клавиатуры, и это проверяет
`/accessibility`.

## 4. Подчёркивание ссылки

Так — нет: `transition: width` и `transition: right` пересчитывают раскладку
на каждом кадре (это ловит `check-anim.sh`).

```css
.nav a::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 2px;
  background: var(--accent);
  transform: scaleX(0); transform-origin: left;
  transition: transform var(--dur-ui) var(--ease);
}
.nav a:hover::after { transform: scaleX(1); }
```

## 5. Шапка при прокрутке

Тень и уплотнение — классом, а не пересчётом высоты:

```js
addEventListener('scroll', () => {
  document.body.classList.toggle('scrolled', scrollY > 24);
}, { passive: true });
```

`{ passive: true }` обязателен: без него браузер ждёт обработчик перед
прокруткой, и на телефоне это чувствуется.

## 6. Аккордеон и вопрос-ответ

`height: auto` не анимируется. Способ без JS-измерений:

```css
.answer { display: grid; grid-template-rows: 0fr;
          transition: grid-template-rows var(--dur-reveal) var(--ease); }
.answer > div { overflow: hidden; }
.item[open] .answer { grid-template-rows: 1fr; }
```

Разметку держать на `<details>/<summary>`: работает без JS, читается
скринридером, индексируется поиском.

## 7. Меню и модальное окно

На React — `AnimatePresence` (иначе элемент исчезает без выхода). Правила
одинаковые для любой реализации: фон затемняется 200 мс, панель приезжает на
16–24 px, фокус уходит внутрь и возвращается назад при закрытии, `Esc`
закрывает, прокрутка страницы под окном блокируется.

## 8. Счётчик цифр

Только если цифра настоящая — из `clients/<домен>/`. Выдуманное «более 500
клиентов» ловится `check-shablon.sh` как «стоп», и накрутка его не спасёт.

```js
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
if (reduce) el.textContent = target;          // сразу конечное значение
else { /* requestAnimationFrame, 800 мс, easeOut */ }
```

Считать от нуля дольше секунды нельзя: человек читает цифру, а не смотрит
мультфильм.

## 9. Форма

Три состояния, и все три обязательны: кнопка в отправке (спиннер и
`disabled`), успех («заявка ушла, перезвоним»), ошибка с человеческим текстом.
Заявка, ушедшая без единого признака жизни, — самая дорогая потеря на сайте
клиента: человек не звонит, потому что уверен, что уже написал.

## 10. Параллакс

`background-attachment: fixed` на iOS не работает и дёргается — не брать.
Если параллакс правда нужен, это `/gsap-scrolltrigger` со `scrub` и
обязательным отключением на узком экране:

```js
ScrollTrigger.matchMedia({
  '(min-width: 768px)': () => { /* только тут */ },
});
```

## 11. Tailwind (проекты из Lovable)

Свои появления — через `tailwind.config.ts`, чтобы не плодить инлайновые
стили:

```ts
extend: {
  keyframes: { reveal: { from: { opacity: '0', transform: 'translateY(16px)' },
                         to:   { opacity: '1', transform: 'none' } } },
  animation: { reveal: 'reveal .4s cubic-bezier(.16,1,.3,1) both' },
}
```

`animate-pulse` и `animate-bounce` из коробки — не украшение, а индикаторы
загрузки. На карточке услуги вечно пульсирующий блок читается как «страница
не догрузилась».

## Чего не делать никогда

- Анимировать заголовок и главную картинку первого экрана (это LCP).
- Ставить движение на `transition: all`.
- Оставлять что-то бесконечно крутящимся в поле зрения.
- Прокрутку «как в кино» с перехватом колеса: пользователь теряет контроль,
  а на трекпаде это ещё и мимо.
- Анимировать появление форм и телефонов: контакт должен быть виден сразу.
