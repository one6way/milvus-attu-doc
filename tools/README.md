# tools — сборка Word-отчёта через OfficeCLI

Генерация отчёта `.docx` из исходного текста (`milvusattugorobec/otchet.txt`) и скриншотов
(`screens/`) с помощью [OfficeCLI](https://github.com/iOfficeAI/OfficeCLI) (iOfficeAI).

## Установка OfficeCLI (Windows)

```powershell
irm https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.ps1 | iex
officecli --version      # 1.0.x
```

## Сборка отчёта

```powershell
# 1) разобрать отчёт на блоки (заголовки/текст/код) + привязать скриншоты к разделам
python tools/report_blocks.py                 # -> tools/blocks.json

# 2) превратить блоки в batch-команды OfficeCLI
python tools/report_officecli_commands.py     # -> tools/commands.json

# 3) собрать .docx
officecli create "ОТЧЁТ_Milvus_банковские_данные.docx"
officecli batch "ОТЧЁТ_Milvus_банковские_данные.docx" --input tools/commands.json
officecli save  "ОТЧЁТ_Milvus_банковские_данные.docx"
officecli validate "ОТЧЁТ_Milvus_банковские_данные.docx"     # Validation passed
```

## Проверка результата

```powershell
officecli view "ОТЧЁТ_Milvus_банковские_данные.docx" stats
officecli view "ОТЧЁТ_Milvus_банковские_данные.docx" screenshot --page 1 -o page1.png
officecli view "ОТЧЁТ_Milvus_банковские_данные.docx" screenshot --grid --page 1-60 -o grid.png
```

## Что попадает в отчёт

- Титульный лист.
- Весь текст отчёта: заголовки (Heading1–3), абзацы, таблицы-подписи, листинги кода (Consolas).
- **24 скриншота** из `screens/` с подписями «Рисунок N — …», привязанные к разделам
  (2.1, 2.3.1–2.3.6, 2.4, 2.7, 2.8, 2.9.1, 3.1, 3.3, 3.4.x, 3.5, 3.6).
- Приложение А — листинги из `listings_script/`.

Итог: ~2780 абзацев, 24 рисунка, размер ~2.6 МБ.

## Соответствие раздел → скриншот

Задаётся словарём `FIG` в `tools/report_blocks.py` — при добавлении нового скриншота
достаточно дописать пару `("Sxx_....png", "подпись")` нужному разделу и пересобрать.

> Замечание: `.docx → .pdf` OfficeCLI не умеет без плагина-экспортёра; для просмотра
> используйте режимы `screenshot` / `html` / `svg` (встроенный HTML-рендерер OfficeCLI).
