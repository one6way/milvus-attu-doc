# -*- coding: utf-8 -*-
"""blocks.json -> commands.json (batch-команды OfficeCLI) для сборки отчёта в .docx."""
import io, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOCKS = os.path.join(ROOT, "tools", "blocks.json")
OUT = os.path.join(ROOT, "tools", "commands.json")
LS = os.path.join(ROOT, "listings_script")

MAX_CM = 15.0  # макс. ширина картинки

def cm(w_px, h_px):
    w = w_px / 96.0 * 2.54
    h = h_px / 96.0 * 2.54
    if w > MAX_CM:
        h = h * MAX_CM / w
        w = MAX_CM
    return f"{w:.2f}cm", f"{h:.2f}cm"

def para(text, **props):
    p = {"text": text}
    p.update(props)
    return {"command": "add", "parent": "/body", "type": "paragraph", "props": p}

blocks = json.load(io.open(BLOCKS, encoding="utf-8"))
cmds = []

def add_para(text, **props):
    cmds.append(para(text, **props))
    return 1  # один абзац

# --- титул ---
cmds.append(para("Информационная система на основе векторной базы данных Milvus",
                 style="Heading1", align="center", size="18pt"))
cmds.append(para("для предметной области «Банковские данные»", align="center", size="16pt", bold=True))
cmds.append(para("Отчёт о научно-исследовательской работе", align="center", size="14pt"))
cmds.append(para("Milvus v3.0.1 (Standalone) + Attu v3.0.1, Docker Desktop", align="center", size="12pt", italic=True))
cmds.append({"command": "add", "parent": "/body", "type": "paragraph",
             "props": {"text": ""}})
cmds.append({"command": "add", "parent": "/body/p[5]", "type": "pagebreak"})

p_idx = 5  # после 5 абзацев титула (pagebreak — это ребёнок абзаца, не новый абзац)

def count_paras(text):
    return max(1, text.count("\n") + 1)

for b in blocks:
    t = b["t"]
    if t in ("h1", "h2", "h3"):
        cmds.append(para(b["text"], style={"h1": "Heading1", "h2": "Heading2", "h3": "Heading3"}[t]))
        p_idx += 1
    elif t == "caption":
        cmds.append(para(b["text"], bold=True, align="center", size="10pt"))
        p_idx += 1
    elif t == "code":
        cmds.append(para(b["text"], font="Consolas", size="8pt"))
        p_idx += count_paras(b["text"])
    elif t == "fig":
        cmds.append(para(""))           # пустой абзац под картинку
        p_idx += 1
        w, h = cm(b.get("w", 1200), b.get("h", 800))
        cmds.append({"command": "add", "parent": f"/body/p[{p_idx}]", "type": "picture",
                     "props": {"src": b["file"], "width": w, "height": h,
                               "alt": b.get("caption", "figure")}})
        cmds.append(para(b.get("caption", ""), italic=True, align="center", size="10pt"))
        p_idx += 1
    else:
        cmds.append(para(b["text"], align="justify"))
        p_idx += 1

# --- Приложение А ---
cmds.append({"command": "add", "parent": "/body", "type": "pagebreak", "props": {}})
p_idx += 0
cmds.append(para("ПРИЛОЖЕНИЕ А. ЛИСТИНГИ ПРОГРАММ", style="Heading1"))
p_idx += 1

APPENDIX = [
    ("А.1. Скрипт развёртывания Milvus Standalone (docker-compose)", ["A1_docker-compose.yml", "A1_milvus-user.yaml"]),
    ("А.2–А.3. Создание коллекций, индексов и генератор банковских данных", ["A2_A3_collections_and_data.py"]),
    ("А.4. Генерация эмбеддингов (E5) — локальный OpenAI-совместимый сервер", ["e5_embed_server.py"]),
    ("А.5. Семантический поиск, категоризация, выявление аномалий", ["A3_A4_A5_embed_search_anomaly.py"]),
    ("А.6. Настройка RBAC и ресурсных групп + проверка доступа", ["A6_rbac.py", "A6b_rbac_check.py"]),
    ("А.7. Проведение экспериментов и сбор метрик", ["A7_benchmark.py"]),
]
for title, files in APPENDIX:
    cmds.append(para(title, style="Heading2")); p_idx += 1
    for f in files:
        p = os.path.join(LS, f)
        if not os.path.exists(p):
            continue
        cmds.append(para(f"Файл: {f}", bold=True, size="10pt")); p_idx += 1
        txt = io.open(p, encoding="utf-8").read()
        cmds.append(para(txt, font="Consolas", size="7pt"))
        p_idx += count_paras(txt)

io.open(OUT, "w", encoding="utf-8").write(json.dumps(cmds, ensure_ascii=False))
print("commands:", len(cmds), "last p_idx:", p_idx)