# -*- coding: utf-8 -*-
"""Собирает report/otchet_v3.txt: исходный отчёт с ЗАМЕНЁННЫМ разделом 3.1.

Раздел «3.1. Развёртывание Milvus Standalone» (вплоть до «3.2. Создание коллекций
и индексов») заменяется текстом из report/part_3_1.txt — развёртывание описано
по репозиторию проекта (docker compose), без сторонних скриптов.

Запуск:  python report/patch_source.py
"""
import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "milvusattugorobec", "otchet.txt")
NEW31 = os.path.join(ROOT, "report", "part_3_1.txt")
OUT = os.path.join(ROOT, "report", "otchet_v3.txt")

lines = io.open(SRC, encoding="utf-8").read().replace("\r\n", "\n").split("\n")

start = next(i for i, l in enumerate(lines) if l.startswith("3.1. Развёртывание Milvus Standalone"))
end = next(i for i, l in enumerate(lines) if l.startswith("3.2. Создание коллекций и индексов"))

new31 = io.open(NEW31, encoding="utf-8").read().rstrip("\n").split("\n")

out = lines[:start] + new31 + [""] + lines[end:]

# вырезаем исходную заглушку ПРИЛОЖЕНИЯ А (его собирает сборщик отчёта) и ИИ-советы
tail_cut = next((i for i, l in enumerate(out) if l.startswith("ПРИЛОЖЕНИЕ А.")), None)
if tail_cut is not None:
    print(f"вырезана исходная заглушка Приложения А: строки {tail_cut + 1}..{len(out)}")
    out = out[:tail_cut]

out = [l for l in out if not l.startswith("Список рекомендуется дополнить")]

io.open(OUT, "w", encoding="utf-8").write("\n".join(out))
print(f"заменён блок 3.1: строк {end - start} -> {len(new31)}")
print("записано:", OUT, len(out), "строк")

