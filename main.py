#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MobilePad: ПК запускает сервер, телефон открывает страницу
с кнопками 3x3, а ПК нажимает горячие клавиши (F13–F24 и другие).

Установка (один раз):
    pip install flask pynput

Запуск:
    python main.py

После запуска в консоли появится адрес вида http://192.168.0.15:5000 —
открой его в браузере телефона (телефон и ПК в одной Wi-Fi сети).
"""

import json
import socket
import threading
import time

from flask import Flask, Response, abort, jsonify
from pynput.keyboard import Controller, Key, KeyCode

# ──────────────────────────────────────────────────────────────────────
# НАСТРОЙКИ — меняй здесь
# ──────────────────────────────────────────────────────────────────────

PORT = 5000

# Страницы кнопок. На каждой странице ровно 9 кнопок (сетка 3x3).
#   label — подпись на кнопке (можно переименовать под свой звук)
#   keys  — что нажать на ПК. Примеры:
#           ["f13"]                — одна клавиша F13
#           ["ctrl", "alt", "num1"] — комбинация Ctrl+Alt+Numpad1
#           ["ctrl", "shift", "a"]  — Ctrl+Shift+A
# Поддерживаются: f1–f24, num0–num9 (цифры на цифровом блоке),
# ctrl, alt, shift и любая одиночная буква или цифра.
PAGES = [   # Структура: {"label": "(Название кнопки)", "keys": ["(клавиши которые нужно нажать"]},
    {
    "name": "Страница 1",
    "buttons": [
        {"label": "Клавиша 1", "keys": ["f13"]},
        {"label": "Клавиша 2", "keys": ["f14"]},
        {"label": "Клавиша 3", "keys": ["f15"]},
        {"label": "Клавиша 4", "keys": ["f16"]},
        {"label": "Клавиша 5", "keys": ["f17"]},
        {"label": "Клавиша 6", "keys": ["f18"]},
        {"label": "Клавиша 7", "keys": ["f19"]},
        {"label": "Клавиша 8", "keys": ["f20"]},
        {"label": "Клавиша 9", "keys": ["f21"]},
    ],
},
    {
    "name": "Страница 2",
    "buttons": [
        {"label": "Клавиша 1", "keys": ["ctrl", "alt", "num1"]},
        {"label": "Клавиша 2", "keys": ["ctrl", "alt", "num2"]},
        {"label": "Клавиша 3", "keys": ["ctrl", "alt", "num3"]},
        {"label": "Клавиша 4", "keys": ["ctrl", "alt", "num4"]},
        {"label": "Клавиша 5", "keys": ["ctrl", "alt", "num5"]},
        {"label": "Клавиша 6", "keys": ["ctrl", "alt", "num6"]},
        {"label": "Клавиша 7", "keys": ["ctrl", "alt", "num7"]},
        {"label": "Клавиша 8", "keys": ["ctrl", "alt", "num8"]},
        {"label": "Клавиша 9", "keys": ["ctrl", "alt", "num9"]},
    ],
},
]

# Сколько миллисекунд держать клавишу нажатой.
HOLD_MS = 50


keyboard = Controller()
press_lock = threading.Lock()  

MODIFIERS = {"ctrl": Key.ctrl, "alt": Key.alt, "shift": Key.shift}


def resolve_key(name):
    """Превращает название клавиши ('f13', 'num1', 'ctrl', 'a') в объект pynput."""
    name = name.lower().strip()

    if name in MODIFIERS:
        return MODIFIERS[name]

    if name.startswith("f") and name[1:].isdigit():
        n = int(name[1:])
        if 1 <= n <= 24:
            return KeyCode.from_vk(0x70 + n - 1)

    if name.startswith("num") and name[3:].isdigit():
        n = int(name[3:])
        if 0 <= n <= 9:
            return KeyCode.from_vk(0x60 + n)

    if len(name) == 1:
        return KeyCode.from_char(name)

    raise ValueError(f"Неизвестная клавиша: {name!r}")


def press_combo(keys):
    """Нажимает и отпускает комбинацию клавиш на уровне системы."""
    resolved = [resolve_key(k) for k in keys]
    with press_lock:
        for k in resolved:
            keyboard.press(k)
        time.sleep(HOLD_MS / 1000)
        for k in reversed(resolved):
            keyboard.release(k)


def check_config():
    """Проверяет настройки при запуске, чтобы ошибка была видна сразу."""
    for page in PAGES:
        if len(page["buttons"]) != 9:
            raise SystemExit(f"На странице «{page['name']}» должно быть 9 кнопок.")
        for button in page["buttons"]:
            for key in button["keys"]:
                resolve_key(key)


# ──────────────────────────────────────────────────────────────────────
# ВЕБ-СТРАНИЦА (открывается на другом устройстве)
# ──────────────────────────────────────────────────────────────────────

PAGE_HTML = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#14171c">
<title>MobilePad</title>
<style>
  :root {
    --bg: #14171c;
    --pad: #232932;
    --pad-hover: #2c343f;
    --text: #e8eaed;
    --muted: #8b93a1;
    --accent: #ffb020;
    --accent-text: #1a1304;
    color-scheme: dark;
  }
  * { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
  html, body { height: 100%; margin: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    display: flex;
    flex-direction: column;
    padding: max(12px, env(safe-area-inset-top)) 12px max(12px, env(safe-area-inset-bottom));
    gap: 12px;
    user-select: none;
    -webkit-user-select: none;
  }
  .tabs { display: flex; gap: 8px; }
  .tab {
    flex: 1;
    padding: 12px 8px;
    border: 0;
    border-radius: 10px;
    background: transparent;
    color: var(--muted);
    font: inherit;
    font-size: 1rem;
    font-weight: 600;
  }
  .tab[aria-selected="true"] { background: var(--pad); color: var(--text); }
  .grid {
    flex: 1;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(3, 1fr);
    gap: 10px;
    min-height: 0;
  }
  .pad {
    border: 0;
    border-radius: 14px;
    background: var(--pad);
    color: var(--text);
    font: inherit;
    font-size: clamp(1rem, 4.5vw, 1.4rem);
    font-weight: 600;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 6px;
    transition: transform 80ms ease, background-color 120ms ease;
  }
  .pad small { font-size: 0.75rem; font-weight: 400; color: var(--muted); }
  .pad:active, .pad.hit { transform: scale(0.96); background: var(--accent); color: var(--accent-text); }
  .pad:active small, .pad.hit small { color: var(--accent-text); }
  .pad:focus-visible, .tab:focus-visible { outline: 3px solid var(--accent); outline-offset: 2px; }
  .status { min-height: 1.2em; text-align: center; font-size: 0.85rem; color: var(--muted); }
  .status.error { color: #ff7a7a; }
  @media (prefers-reduced-motion: reduce) { .pad { transition: none; } }
</style>
</head>
<body>
  <div class="tabs" role="tablist" id="tabs"></div>
  <div class="grid" id="grid"></div>
  <div class="status" id="status" role="status"></div>

<script>
  const PAGES = __PAGES__;
  let current = 0;

  const tabsEl = document.getElementById("tabs");
  const gridEl = document.getElementById("grid");
  const statusEl = document.getElementById("status");

  function showStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.className = "status" + (isError ? " error" : "");
  }

  // Рисует вкладки (показываем их только если страниц больше одной).
  function renderTabs() {
    tabsEl.innerHTML = "";
    if (PAGES.length < 2) { tabsEl.style.display = "none"; return; }
    PAGES.forEach((page, i) => {
      const tab = document.createElement("button");
      tab.className = "tab";
      tab.setAttribute("role", "tab");
      tab.setAttribute("aria-selected", i === current ? "true" : "false");
      tab.textContent = page.name;
      tab.onclick = () => { current = i; renderTabs(); renderGrid(); showStatus("", false); };
      tabsEl.appendChild(tab);
    });
  }

  // Рисует сетку 3x3 для текущей страницы.
  function renderGrid() {
    gridEl.innerHTML = "";
    PAGES[current].buttons.forEach((button, i) => {
      const pad = document.createElement("button");
      pad.className = "pad";
      pad.innerHTML = "<span></span><small></small>";
      pad.children[0].textContent = button.label;
      pad.children[1].textContent = button.hint;
      pad.onclick = () => press(pad, current, i, button.label);
      gridEl.appendChild(pad);
    });
  }

  async function press(pad, page, index, label) {
    if (navigator.vibrate) navigator.vibrate(20);
    pad.classList.add("hit");
    setTimeout(() => pad.classList.remove("hit"), 150);
    try {
      const response = await fetch("/api/press/" + page + "/" + index, { method: "POST" });
      if (!response.ok) throw new Error("HTTP " + response.status);
      showStatus("Нажато: " + label, false);
    } catch (error) {
      showStatus("Нет связи с ПК. Проверь, что main.py запущен и Wi-Fi общий.", true);
    }
  }

  renderTabs();
  renderGrid();
</script>
</body>
</html>
"""


def build_page():
    """Подставляет в страницу названия кнопок (сами клавиши телефону не отправляются)."""
    pages_for_browser = [
        {
            "name": page["name"],
            "buttons": [
                {"label": b["label"], "hint": "+".join(k.upper() for k in b["keys"])}
                for b in page["buttons"]
            ],
        }
        for page in PAGES
    ]
    return PAGE_HTML.replace("__PAGES__", json.dumps(pages_for_browser, ensure_ascii=False))


# ──────────────────────────────────────────────────────────────────────
# СЕРВЕР
# ──────────────────────────────────────────────────────────────────────

app = Flask(__name__)


@app.get("/")
def index():
    return Response(build_page(), mimetype="text/html")


@app.post("/api/press/<int:page>/<int:index>")
def api_press(page, index):
    if page >= len(PAGES) or index >= len(PAGES[page]["buttons"]):
        abort(404)
    press_combo(PAGES[page]["buttons"][index]["keys"])
    return jsonify(ok=True)


def get_local_ip():
    """Узнаёт адрес ПК в домашней сети (пакеты при этом не отправляются)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


if __name__ == "__main__":
    check_config()
    ip = get_local_ip()
    print()
    print("MobilePad запущен.")
    print(f"Открой на телефоне: http://{ip}:{PORT}")
    print("Телефон и ПК должны быть в одной Wi-Fi сети. Остановить: Ctrl+C")
    print()
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
