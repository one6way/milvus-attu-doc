# -*- coding: utf-8 -*-
"""Мини-сервер OpenAI-совместимых эмбеддингов — альтернатива LM Studio.

Зачем: Attu для кнопки "Embed text/image" должен считать вектор ТОЙ ЖЕ моделью,
что и документы (text-embedding-nomic-embed-text-v1.5, префикс 'search_query:'),
иначе поиск не совпадёт.

Основной путь проекта — LM Studio (раздел 3.3.0 отчёта); этот скрипт нужен, если
LM Studio недоступен и модель нужно поднять локально из Python.

Эндпоинты: POST /v1/embeddings и POST /embeddings
Тело:      {"model": "...", "input": "текст" | ["текст", ...]}
Ответ:     {"object":"list","data":[{"object":"embedding","index":i,"embedding":[...]}], ...}

Префикс (--prefix) сервер добавляет к каждому тексту сам:
  * "search_query: " (по умолчанию) — для кнопки Attu «Embed text»;
  * ""                     — когда префикс задаёт вызывающая сторона
                             (скрипты отчёта S09/S10/S11/S16 и A3..A5
                              сами добавляют search_query:/search_document:).

Запуск:
  python scripts/embed_server_local.py --port 8091
  python scripts/embed_server_local.py --port 8091 --prefix ""
"""
import argparse, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = None
MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
PREFIX = "search_query: "  # Attu шлёт текст запроса -> префикс поискового запроса


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/models"):
            self._send(200, {"object": "list", "data": [
                {"id": MODEL_NAME, "object": "model", "owned_by": "local"}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.rstrip("/").endswith("/embeddings"):
            self._send(404, {"error": "use /v1/embeddings"})
            return
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            self._send(400, {"error": f"bad json: {e}"})
            return
        inp = req.get("input", "")
        texts = inp if isinstance(inp, list) else [inp]
        texts = [PREFIX + t for t in texts]
        vecs = MODEL.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        data = [{"object": "embedding", "index": i, "embedding": [float(x) for x in v]}
                for i, v in enumerate(vecs)]
        self._send(200, {"object": "list", "data": data,
                         "model": MODEL_NAME, "usage": {"prompt_tokens": 0, "total_tokens": 0}})


def main():
    global MODEL, MODEL_NAME, PREFIX
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--model", default=MODEL_NAME)
    ap.add_argument("--prefix", default=PREFIX,
                    help="префикс, добавляемый сервером к каждому тексту "
                         "(пустая строка — если префикс задаёт вызывающая сторона)")
    args = ap.parse_args()

    MODEL_NAME = args.model
    PREFIX = args.prefix
    from sentence_transformers import SentenceTransformer
    # trust_remote_code не нужен: nomic-bert поддержан в transformers (>=4.48) нативно,
    # а remote-код модели рассчитан на transformers 4.x и на 5.x падает.
    print(f"[embed-server] загружаю {MODEL_NAME} ...", flush=True)
    MODEL = SentenceTransformer(MODEL_NAME)
    print(f"[embed-server] слушаю 0.0.0.0:{args.port}  (POST /v1/embeddings, prefix={PREFIX!r})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()