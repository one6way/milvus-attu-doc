# -*- coding: utf-8 -*-
"""Мини-сервер OpenAI-совместимых эмбеддингов на intfloat/multilingual-e5-base (как в отчёте).

Зачем: Attu для кнопки "Embed text/image" должен считать вектор ТОЙ ЖЕ моделью,
что и документы (E5, префикс 'query: '), иначе поиск не совпадёт.

Эндпоинты: POST /v1/embeddings и POST /embeddings
Тело:      {"model": "...", "input": "текст" | ["текст", ...]}
Ответ:     {"object":"list","data":[{"object":"embedding","index":i,"embedding":[...]}], ...}

Запуск:
  python listings_script/e5_embed_server.py --port 8091
"""
import argparse, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODEL = None
MODEL_NAME = "intfloat/multilingual-e5-base"
PREFIX = "query: "  # Attu шлёт текст запроса -> префикс запроса E5


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
    global MODEL, MODEL_NAME
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8091)
    ap.add_argument("--model", default=MODEL_NAME)
    args = ap.parse_args()

    MODEL_NAME = args.model
    from sentence_transformers import SentenceTransformer
    print(f"[e5-server] загружаю {MODEL_NAME} ...", flush=True)
    MODEL = SentenceTransformer(MODEL_NAME)
    print(f"[e5-server] слушаю 0.0.0.0:{args.port}  (POST /v1/embeddings, prefix={PREFIX!r})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()