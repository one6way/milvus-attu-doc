# tools — сборка Word-отчёта через OfficeCLI

Генерация отчёта `.docx` из исходного текста (`milvusattugorobec/otchet.txt`) и скриншотов
(`screens/`) с помощью [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) (iOfficeAI).

## Установка OfficeCLI (Windows)

```powershell
irm https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.ps1 | iex
officecli --version      # 1.0.x
```

## Сборка отчёта (одна команда)

```powershell
python tools/make_report.py
```

Скрипт сам:
1. разбирает `milvusattugorobec/otchet.txt` на блоки (заголовки, абзацы, **таблицы**, **формулы**, листинги);
2. строит batch-команды OfficeCLI (`tools/commands.json`);
3. создаёт `.docx`, применяет команды (`officecli batch`);
4. вставляет **24 скриншота** в абзацы-маркеры по `paraId` (второй batch);
5. сохраняет и валидирует (`officecli validate`).

Результат: `ОТЧЁТ_Milvus_банковские_данные.docx`.

## Что попадает в отчёт

- Титульный лист.
- Текст отчёта: заголовки (Heading1–3), абзацы, подписи таблиц, листинги кода (Consolas).
- **25 настоящих Word-таблиц** (не текст!): шапка жирным, рамки, автоподбор ширины колонок.
- **47 формул** — как объекты Equation (OMML), режим display (напр. `||a − b||² = 2 − 2·cos(a, b)`).
- **24 скриншота** из `screens/` с подписями «Рисунок N — …», привязанные к разделам
  (2.1, 2.3.1–2.3.6, 2.4, 2.7, 2.8, 2.9.1, 3.1, 3.3, 3.4.x, 3.5, 3.6).
- Приложение А — листинги из `listings_script/`.

## Проверка результата

```powershell
officecli view "ОТЧЁТ_Milvus_банковские_данные.docx" stats
officecli query "ОТЧЁТ_Milvus_банковские_данные.docx" table --json      # таблицы
officecli query "ОТЧЁТ_Milvus_банковские_данные.docx" equation --json   # формулы
officecli view "ОТЧЁТ_Milvus_банковские_данные.docx" screenshot --page 6 -o page6.png
officecli view "ОТЧЁТ_Milvus_банковские_данные.docx" screenshot --grid --page 1-70 -o grid.png
```

## Соответствие раздел → скриншот

Задаётся словарём `FIG` в `tools/make_report.py` — допишите пару `("Sxx_....png", "подпись")`
нужному разделу и пересоберите.

> Замечание: `.docx → .pdf` OfficeCLI не умеет без плагина-экспортёра; для просмотра
> используйте режимы `screenshot` / `html` / `svg` (встроенный HTML-рендерер OfficeCLI).
