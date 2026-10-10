# -*- coding: utf-8 -*-
"""Сборка Word-отчёта через OfficeCLI: текст + НАСТОЯЩИЕ таблицы + формулы + скриншоты.

Запуск (из корня репозитория):
    python tools/make_report.py

Требуется установленный OfficeCLI (см. tools/README.md).
"""
import io, json, os, re, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "milvusattugorobec", "otchet.txt")
SHOTS = os.path.join(ROOT, "screens")
LS = os.path.join(ROOT, "listings_script")
OUT_DOCX = os.path.join(ROOT, "ОТЧЁТ_Milvus_банковские_данные.docx")
WORK = os.path.join(ROOT, "tools")

H1 = re.compile(r"^(\d+)\.\s+(\S.*)$")
H2 = re.compile(r"^(\d+\.\d+)\.\s+(\S.*)$")
H3 = re.compile(r"^(\d+\.\d+\.\d+)\.\s+(\S.*)$")
CAPTION = re.compile(r"^(Таблица|Рисунок)\s+\d")
CAPS_TITLE = re.compile(r"^(ВВЕДЕНИЕ|ЗАКЛЮЧЕНИЕ|СОДЕРЖАНИЕ|АННОТАЦИЯ|РЕФЕРАТ|"
                        r"СПИСОК ИСПОЛЬЗОВАННЫХ ИСТОЧНИКОВ|ПРИЛОЖЕНИЕ\s+[А-ЯA-Z].*)$")
CODEMARK = {"python", "bash", "yaml", "json", "powershell", "shell", "text", "sql", "js", "javascript"}
MATHSYM = set("=≈≤≥∈·×²√θμσΣ‖∝∫∑")
CODECHARS = set("=(){}[]<>;")

# эмодзи и служебные символы (❗❕⛔✅✔⚠🔴 и т.п.), но БЕЗ стрелок, тире и матзнаков
EMOJI_RE = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # эмодзи-блоки
    "\u2600-\u27BF"           # ☢ ⚔ ✅ ✔ ❗ ❕ ⛔ ⚠ и др.
    "\u2B00-\u2BFF"           # ⬛⭐ и др.
    "\u203C\u2049\u2122\u2139"
    "\uFE0E\uFE0F\u200D"      # вариационные селекторы/ZWJ
    "\u2753-\u2757"           # ?❗❗
    "]"
)
REDLINE_BILO = re.compile(r"^[\s#\"'\-–—]*(?:БЫЛО)\b", re.S)
REDLINE_STALO = re.compile(r"^[\s#\"'\-–—]*(?:СТАЛО)\b[^:.!]{0,90}[.:]\s*", re.S)
WORD_MARK = re.compile(r"\b(?:БЫЛО|СТАЛО)\b")


def clean_inline(s):
    s = EMOJI_RE.sub("", s)
    s = s.replace("\u00a0", " ").replace("\u2216", "")
    s = WORD_MARK.sub("", s)
    s = re.sub(r"\s+([,.;:)])", r"\1", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def clean_code_line(s):
    if REDLINE_BILO.match(s):
        return None                      # строку-маркер БЫЛО выбросить
    s = EMOJI_RE.sub("", s).replace("\u00a0", " ")
    s = REDLINE_STALO.sub("", s)
    s = WORD_MARK.sub("", s)
    return s.rstrip()


def strip_redline(s):
    """БЫЛО ... -> None (выбросить); СТАЛО (...): текст -> текст."""
    s = s.strip()
    if REDLINE_BILO.match(s) or "БЫЛО" in s[:120]:
        return None
    return REDLINE_STALO.sub("", s)

FIG = {
    "2.1":  [("S01_cluster_overview.png", "Milvus Standalone v3.0.1 в Attu: режим развёртывания и узлы")],
    "2.3":  [("S02_collections.png", "Список созданных коллекций банковской системы")],
    "2.3.1": [("S03_schema_products.png", "Схема коллекции BankingProducts (вектор description_vector, dim=768)")],
    "2.3.2": [("S14_schema_clients.png", "Схема коллекции Clients (техническое поле _tech_vector)")],
    "2.3.3": [("S17_schema_currencies.png", "Схема коллекции Currencies")],
    "2.3.4": [("S18_schema_accounts.png", "Схема коллекции Accounts")],
    "2.3.5": [("S19_schema_cards.png", "Схема коллекции Cards")],
    "2.3.6": [("S13_schema_transactions.png", "Схема коллекции Transactions (purpose_vector, dim=768)")],
    "2.4":  [("S15_index_products.png", "Индексы BankingProducts: HNSW/COSINE, INVERTED, STL_SORT"),
             ("S20_index_transactions.png", "Индексы Transactions")],
    "2.7":  [("S06_users.png", "Пользователи admin_user/analyst_user/viewer_user и их роли"),
             ("S07_roles.png", "Роли: analyst (+7 прав) и viewer (+2 права)"),
             ("S21_role_privileges.png", "Детализация прав ролей и ресурсные группы")],
    "2.8":  [("S24_resource_groups.png", "Ресурсные группы: default, rg_high_priority, rg_low_priority")],
    "2.9.1": [("S05_search_products.png", "Семантический поиск продуктов в Attu (модель E5)")],
    "3.1":  [("S00_login.png", "Вход в веб-интерфейс Attu")],
    "3.3":  [("S04_data_products.png", "Загруженные данные коллекции BankingProducts"),
             ("S09_embedding_e5_test.png", "Проверка подключения провайдера эмбеддингов E5"),
             ("S10_embedding_providers.png", "Настроенные провайдеры эмбеддингов")],
    "3.4.2": [("S16_search_transactions.png", "Поиск похожих назначений платежей (Transactions)")],
    "3.4.3": [("S25_anomaly_lowsim.png", "Сценарий аномалии: запрос не по теме, низкие значения сходства"),
              ("S22_search_tx_anomalies.png", "Вывод скрипта: поиск, категоризация, аномалии (θ = μ−2σ)")],
    "3.5":  [("S23_rbac_verification.png", "Проверка разграничения доступа реальными данными")],
    "3.6":  [("S08_metrics.png", "Результаты экспериментов: efConstruction, ef, индексы, фильтры, метрики")],
}


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")


def is_prose(s):
    t = s.strip()
    if not t or t.startswith(("#", "//", "-", "*")):
        return False
    if any(c in CODECHARS for c in t):
        return False
    return t.endswith((".", "!", "?", ":")) and len(t.split()) >= 4


def is_formula(raw):
    """Строка-формула: с отступом, короткая, со знаком = и матсимволом, без длинных фраз."""
    st = raw.strip()
    if not raw.startswith("  ") or len(st) > 90:
        return False
    if not any(ch in st for ch in MATHSYM):
        return False
    if "=" not in st and "≈" not in st:
        return False
    cyr = len(re.findall(r"[А-Яа-яЁё]{2,}", st))
    return cyr <= 3


def parse():
    raw = io.open(SRC, encoding="utf-8").read().replace("\r\n", "\n")
    lines = raw.split("\n")
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip().startswith("Информационная система на основе векторной базы данных Milvus"):
            start = i
            break
    lines = lines[start:]

    blocks, code, table = [], [], []
    in_code = False

    def flush_code():
        nonlocal code, in_code
        if code:
            blocks.append({"t": "code", "text": "\n".join(code).rstrip()})
            code = []
        in_code = False

    def flush_table():
        nonlocal table
        if len(table) >= 2:
            blocks.append({"t": "table", "rows": [r for r in table]})
        elif table:
            for r in table:
                blocks.append({"t": "p", "text": "\t".join(r)})
        table = []

    def add_figs(num):
        for fn, cap in FIG.get(num, []):
            p = os.path.join(SHOTS, fn)
            if os.path.exists(p):
                w, h = png_size(p)
                blocks.append({"t": "fig", "file": p, "caption": cap, "w": w, "h": h})

    for ln in lines:
        s = ln.rstrip()
        st = s.strip()

        if "\t" in st and not in_code:
            table.append([c.strip() for c in st.split("\t")])
            continue
        flush_table()

        m = H3.match(st) or H2.match(st) or H1.match(st)
        if m:
            flush_code()
            num, title = m.group(1), m.group(2)
            blocks.append({"t": "h%d" % (num.count(".") + 1), "num": num, "text": f"{num}. {title}"})
            add_figs(num)
            continue
        if CAPS_TITLE.match(st):
            flush_code()
            blocks.append({"t": "h1", "num": "", "text": st})
            continue
        if st.lower() in CODEMARK:
            flush_code()
            in_code = True
            continue
        if not st:
            if in_code:
                code.append("")
            continue
        if in_code:
            if is_prose(st):
                flush_code()
                blocks.append({"t": "p", "text": st})
            else:
                code.append(s)
            continue
        if is_formula(s):
            blocks.append({"t": "formula", "text": st.rstrip(",.;")})
            continue
        if CAPTION.match(st):
            blocks.append({"t": "caption", "text": st})
            continue
        blocks.append({"t": "p", "text": st})

    flush_table()
    flush_code()
    return blocks


MAX_CM = 15.0

def cm_wh(w_px, h_px):
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


def col_widths(rows, total=8300):
    ncol = max(len(r) for r in rows)
    lens = [0] * ncol
    for r in rows:
        for i, c in enumerate(r):
            lens[i] = max(lens[i], len(c))
    s = sum(lens) or 1
    ws = [max(900, int(total * l / s)) for l in lens]
    k = total / sum(ws)
    return [max(900, int(w * k)) for w in ws]


def clean_blocks(blocks):
    """Убрать разметку правок (БЫЛО/СТАЛО) и эмодзи."""
    out, dropped = [], 0
    for b in blocks:
        t = b["t"]
        if t in ("p", "caption"):
            s = strip_redline(b["text"])
            if s is None:
                dropped += 1
                continue
            s = clean_inline(s)
            if not s:
                continue
            out.append({"t": t, "text": s})
        elif t in ("h1", "h2", "h3"):
            out.append({"t": t, "num": b.get("num", ""), "text": clean_inline(b["text"])})
        elif t == "formula":
            out.append({"t": "formula", "text": clean_inline(b["text"])})
        elif t == "code":
            lines = [x for x in (clean_code_line(l) for l in b["text"].split("\n")) if x is not None]
            txt = "\n".join(lines).strip("\n")
            if txt.strip():
                out.append({"t": "code", "text": txt})
        elif t == "table":
            rows = []
            for r in b["rows"]:
                cells = []
                for c in r:
                    cc = strip_redline(c)
                    cells.append(clean_inline(cc if cc is not None else ""))
                rows.append(cells)
            out.append({"t": "table", "rows": rows})
        else:
            out.append(b)
    return out, dropped


def build(blocks):
    cmds, figures = [], []

    # титул
    cmds.append(para("Информационная система на основе векторной базы данных Milvus",
                     style="Heading1", align="center", size="18pt"))
    cmds.append(para("для предметной области «Банковские данные»", align="center", size="16pt", bold=True))
    cmds.append(para("Отчёт о научно-исследовательской работе", align="center", size="14pt"))
    cmds.append(para("Milvus v3.0.1 (Standalone) + Attu v3.0.1, Docker Desktop", align="center", size="12pt", italic=True))
    cmds.append(para("", **{}))

    tidx = 0
    for b in blocks:
        t = b["t"]
        if t in ("h1", "h2", "h3"):
            cmds.append(para(b["text"], style={"h1": "Heading1", "h2": "Heading2", "h3": "Heading3"}[t]))
        elif t == "caption":
            cmds.append(para(b["text"], bold=True, align="center", size="10pt"))
        elif t == "code":
            cmds.append(para(b["text"], font="Consolas", size="8pt"))
        elif t == "formula":
            cmds.append({"command": "add", "parent": "/body", "type": "equation",
                         "props": {"formula": b["text"], "mode": "display"}})
        elif t == "table":
            rows = b["rows"]
            tidx += 1
            cmds.append({"command": "add", "parent": "/body", "type": "table",
                         "props": {"border.all": "single",
                                   "colWidths": ",".join(str(x) for x in col_widths(rows))}})
            for ri, row in enumerate(rows):
                if ri > 0:
                    cmds.append({"command": "add", "parent": f"/body/tbl[{tidx}]", "type": "row"})
                for ci in range(len(col_widths(rows))):
                    cell = row[ci] if ci < len(row) else ""
                    props = {"text": cell}
                    if ri == 0:
                        props["bold"] = True
                    cmds.append({"command": "set",
                                 "path": f"/body/tbl[{tidx}]/tr[{ri+1}]/tc[{ci+1}]/p[1]",
                                 "props": props})
        elif t == "fig":
            marker = "FIGMARK::" + os.path.basename(b["file"])
            cmds.append(para(marker))
            figures.append({"marker": marker, "file": b["file"], "caption": b["caption"],
                            "w": b.get("w", 1200), "h": b.get("h", 800)})
            cmds.append(para(b["caption"], italic=True, align="center", size="10pt"))
        else:
            cmds.append(para(b["text"], align="justify"))

    # Приложение А
    cmds.append({"command": "add", "parent": "/body", "type": "paragraph",
                 "props": {"text": "ПРИЛОЖЕНИЕ А. ЛИСТИНГИ ПРОГРАММ", "style": "Heading1"}})
    APPENDIX = [
        ("А.1. Скрипт развёртывания Milvus Standalone (docker-compose)", ["A1_docker-compose.yml", "A1_milvus-user.yaml"]),
        ("А.2–А.3. Создание коллекций, индексов и генератор банковских данных", ["A2_A3_collections_and_data.py"]),
        ("А.4. Генерация эмбеддингов (E5) — локальный OpenAI-совместимый сервер", ["e5_embed_server.py"]),
        ("А.5. Семантический поиск, категоризация, выявление аномалий", ["A3_A4_A5_embed_search_anomaly.py"]),
        ("А.6. Настройка RBAC и ресурсных групп + проверка доступа", ["A6_rbac.py", "A6b_rbac_check.py"]),
        ("А.7. Проведение экспериментов и сбор метрик", ["A7_benchmark.py"]),
    ]
    for title, files in APPENDIX:
        cmds.append(para(title, style="Heading2"))
        for f in files:
            p = os.path.join(LS, f)
            if not os.path.exists(p):
                continue
            cmds.append(para(f"Файл: {f}", bold=True, size="10pt"))
            cmds.append(para(io.open(p, encoding="utf-8").read(), font="Consolas", size="7pt"))
    return cmds, figures


def find_officecli():
    exe = shutil.which("officecli")
    if exe:
        return exe
    cand = os.path.join(os.environ.get("LOCALAPPDATA", ""), "officecli", "officecli.exe")
    if os.path.exists(cand):
        return cand
    raise SystemExit("officecli не найден. Установите: irm https://raw.githubusercontent.com/iOfficeAI/OfficeCLI/main/install.ps1 | iex")


def run(exe, *args):
    r = subprocess.run([exe, *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("ERR:", " ".join(args)[:120])
        print((r.stdout or "")[-500:], (r.stderr or "")[-500:])
    return r


def kill_officecli():
    """Снять resident-процессы OfficeCLI, которые держат файл открытым."""
    subprocess.run(["taskkill", "/IM", "officecli.exe", "/F"],
                   capture_output=True, text=True)


def pick_out():
    """Целевой файл; если занят (открыт в Word) — пишем рядом с суффиксом _new."""
    if os.path.exists(OUT_DOCX):
        try:
            os.remove(OUT_DOCX)
        except PermissionError:
            alt = OUT_DOCX.replace(".docx", "_new.docx")
            print("ВНИМАНИЕ: файл занят (открыт в Word) -> результат в", os.path.basename(alt))
            if os.path.exists(alt):
                try:
                    os.remove(alt)
                except PermissionError:
                    alt = OUT_DOCX.replace(".docx", "_new2.docx")
            return alt
    return OUT_DOCX


def main():
    exe = find_officecli()
    print("officecli:", exe)
    kill_officecli()

    blocks = parse()
    blocks, dropped = clean_blocks(blocks)
    print("dropped БЫЛО/empty blocks:", dropped)
    from collections import Counter
    print("blocks:", Counter(x["t"] for x in blocks))
    cmds, figures = build(blocks)
    print("commands (phase A):", len(cmds), "figures:", len(figures))

    cmds_path = os.path.join(WORK, "commands.json")
    io.open(cmds_path, "w", encoding="utf-8").write(json.dumps(cmds, ensure_ascii=False))

    out = pick_out()

    run(exe, "create", out)
    r = run(exe, "batch", out, "--input", cmds_path)
    tail = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
    print("batch A:", tail)
    if "0 failed" not in tail:
        print("!!! ошибки в batch A — прерываю")
        return 1

    # --- phase B: картинки по маркерам (путь по paraId) ---
    q = run(exe, "query", out, "paragraph", "--json")
    data = json.loads(q.stdout)
    by_text = {}
    for item in data.get("data", {}).get("results", []):
        by_text.setdefault(item.get("text", ""), item.get("path"))
    print("query matches:", len(by_text))

    bcmds = []
    for f in figures:
        path = by_text.get(f["marker"])
        if not path:
            print("marker not found:", f["marker"])
            continue
        w, h = cm_wh(f["w"], f["h"])
        bcmds.append({"command": "add", "parent": path, "type": "picture",
                      "props": {"src": f["file"], "width": w, "height": h, "alt": f["caption"]}})
        bcmds.append({"command": "remove", "path": path + "/r[1]"})
    bp = os.path.join(WORK, "commands_figs.json")
    io.open(bp, "w", encoding="utf-8").write(json.dumps(bcmds, ensure_ascii=False))
    r = run(exe, "batch", out, "--input", bp)
    tail = (r.stdout or "").strip().splitlines()[-1] if r.stdout else ""
    print("batch B (pictures):", tail)

    run(exe, "save", out)
    r = run(exe, "validate", out)
    print("validate:", (r.stdout or "").strip().splitlines()[0] if r.stdout else "?")
    r = run(exe, "view", out, "stats")
    print((r.stdout or "").strip())
    run(exe, "close", out)
    print("WROTE", out, os.path.getsize(out), "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())

