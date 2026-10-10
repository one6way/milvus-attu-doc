"""Общие утилиты для проверки кода из отчёта на живом стенде Milvus.

Стенд: docker compose из корня репозитория (Milvus standalone + Attu),
креды root/MilvusDemo123, gRPC на 127.0.0.1:19530.
"""

from __future__ import annotations

import contextlib
import os
import sys
import time
from pathlib import Path
from typing import Callable

from pymilvus import DataType, MilvusClient

# Целевой стенд можно переопределить через окружение — чтобы одним и тем же
# харнессом прогонять и наш Milvus v3.0.1, и Milvus v2.6.11 из отчёта.
URI = os.environ.get("MILVUS_URI", "http://127.0.0.1:19530")
ROOT_USER = os.environ.get("MILVUS_USER", "root")
ROOT_PASSWORD = os.environ.get("MILVUS_PASSWORD", "MilvusDemo123")

RESULTS: list[tuple[str, bool, str]] = []


class _Tee:
    """Дублирует вывод в консоль и в UTF-8-файл (консоль Windows искажает кириллицу)."""

    def __init__(self, *streams):
        self._streams = streams

    def write(self, data):
        for stream in self._streams:
            try:
                stream.write(data)
            except Exception:  # noqa: BLE001
                pass

    def flush(self):
        for stream in self._streams:
            try:
                stream.flush()
            except Exception:  # noqa: BLE001
                pass


def start_log(script_file: str) -> str:
    """Включает логирование stdout в <script>.log рядом со скриптом. Возвращает путь."""
    path = Path(script_file).with_suffix(".log")
    handle = open(path, "w", encoding="utf-8")  # noqa: SIM115 — живёт до конца процесса
    sys.stdout = _Tee(sys.__stdout__, handle)
    sys.stderr = _Tee(sys.__stderr__, handle)
    return str(path)


def client(user: str = ROOT_USER, password: str = ROOT_PASSWORD, uri: str = URI) -> MilvusClient:
    return MilvusClient(uri=uri, user=user, password=password)


@contextlib.contextmanager
def probe(name: str, expect_fail: bool = False):
    """Выполняет блок кода и печатает OK/FAIL с текстом ошибки Milvus.

    expect_fail=True — падение ожидается: это фиксируемая ошибка самого отчёта.
    """
    print(f"\n=== {name} ===")
    try:
        yield
    except Exception as exc:  # noqa: BLE001 — нужен любой текст ошибки
        msg = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:400]
        status = "EXPECTED-FAIL" if expect_fail else "FAIL"
        print(f"[{status}] {msg}")
        RESULTS.append((name, expect_fail, msg))
    else:
        if expect_fail:
            print("[UNEXPECTED-OK] вызов прошёл, хотя ожидалась ошибка")
            RESULTS.append((name, False, "ожидалась ошибка Milvus, но вызов прошёл без ошибки"))
        else:
            print("[OK]")
            RESULTS.append((name, True, ""))


def timed(fn: Callable[[], None]) -> float:
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000.0


def drop_if_exists(c: MilvusClient, name: str) -> None:
    if c.has_collection(collection_name=name):
        c.drop_collection(collection_name=name)


def summary() -> int:
    print("\n" + "=" * 78)
    bad = [r for r in RESULTS if not r[1]]
    print(f"ИТОГО: {len(RESULTS) - len(bad)}/{len(RESULTS)} проверок прошло, проблем: {len(bad)}")
    for name, good, msg in RESULTS:
        mark = "OK  " if good else "FAIL"
        print(f"  [{mark}] {name}" + (f" :: {msg}" if msg else ""))
    print("=" * 78)
    return 0 if not bad else 1


def report_vector(dim: int, seed: int = 0) -> list[float]:
    """Детерминированный единичный вектор размерности dim (замена эмбеддинга)."""
    import numpy as np

    rng = np.random.default_rng(seed)
    v = rng.normal(size=dim).astype("float32")
    v /= np.linalg.norm(v)
    return v.tolist()


__all__ = [
    "DataType",
    "MilvusClient",
    "URI",
    "ROOT_USER",
    "ROOT_PASSWORD",
    "RESULTS",
    "client",
    "probe",
    "timed",
    "drop_if_exists",
    "summary",
    "report_vector",
    "start_log",
]