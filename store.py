"""
store.py · история измерений
═══════════════════════════════════════════════════════════════════
Хранит каждый замер индекса навсегда. Это то, что превращает прибор
в прибор: без истории у тебя есть число; с историей — дельта, тренд и
возможность через полгода проверить, соврали мы или нет.

Требования SPEC (R2, R3, R5, R7):
  R2 — история: ответ «что было вчера» = запрос к базе, не к памяти
  R3 — дельта, а не уровень: главный вывод — изменение
  R5 — проверяемость: любой может пересчитать из исходных записей
  R7 — у каждой метрики своё окно

Формат: SQLite. Одна таблица, одна строка на замер. Простой, открытый,
читается без наших библиотек — это часть проверяемости.
"""
from __future__ import annotations
import sqlite3, json, time
from pathlib import Path

DB = Path(__file__).parent / "data" / "measurements.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS measurements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,          -- ISO время замера
    token         TEXT    NOT NULL,
    window_start  INTEGER NOT NULL,          -- unix, начало окна наблюдения
    window_span   INTEGER NOT NULL,          -- длительность окна, сек
    sample_size   INTEGER NOT NULL,          -- уникальных переводов в выборке
    dup_rate      REAL    NOT NULL DEFAULT 0,-- доля дублей (должна быть 0)
    idx_value     REAL    NOT NULL,          -- индекс реальности 0..100 (index зарезервировано в SQLite)
    verdict       TEXT    NOT NULL,
    total_usd     REAL    NOT NULL,
    median_usd    REAL    NOT NULL,
    senders       INTEGER NOT NULL,
    raw           TEXT    NOT NULL           -- полный JSON замера (R5)
);
CREATE INDEX IF NOT EXISTS idx_ts ON measurements(token, ts);

-- источники: откуда взята каждая цифра (R4 — честная метка)
CREATE TABLE IF NOT EXISTS provenance (
    measurement_id INTEGER NOT NULL,
    field          TEXT    NOT NULL,
    label          TEXT    NOT NULL,          -- FACT | ESTIMATE | UNVERIFIED | FORECAST
    source         TEXT    NOT NULL,
    FOREIGN KEY (measurement_id) REFERENCES measurements(id)
);
"""

def connect() -> sqlite3.Connection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB)
    c.executescript(SCHEMA)
    c.commit()
    return c

def save(rep: dict, token: str = "USDC", dup_rate: float = 0.0) -> int:
    """Сохранить замер. Возвращает id. Повторный замер того же часа — новый id,
    история не перезаписывается (это и есть R2)."""
    w = rep.get("window", {})
    v = rep.get("value", {})
    c = rep.get("counts", {})
    conn = connect()
    cur = conn.execute(
        """INSERT INTO measurements
           (ts, token, window_start, window_span, sample_size, dup_rate, idx_value,
            verdict, total_usd, median_usd, senders, raw)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (rep["ts"], token, w.get("from", 0), w.get("span_seconds", 0),
         c.get("transfers", 0), dup_rate, rep["reality_index"], rep["verdict"],
         v.get("total_usd", 0), v.get("median_usd", 0), c.get("senders", 0),
         json.dumps(rep, ensure_ascii=False)),
    )
    mid = cur.lastrowid
    for field, label, source in [
        ("index",  "ESTIMATE",  "собственная формула индекса (см. indexer.analyse)"),
        ("value",  "FACT",      f"eth_getLogs по контракту {token}, сеть Ethereum"),
        ("window", "FACT",      "блоки, выбранные по fromBlock/toBlock"),
        ("agent",  "UNVERIFIED","признаки агентности эвристические, адреса агентов неизвестны"),
    ]:
        conn.execute("INSERT INTO provenance VALUES (?,?,?,?)", (mid, field, label, source))
    conn.commit()
    conn.close()
    return mid

def history(token: str = "USDC", limit: int = 60) -> list[dict]:
    conn = connect()
    rows = conn.execute(
        "SELECT id, ts, idx_value, total_usd, median_usd, sample_size, window_span, verdict "
        "FROM measurements WHERE token=? ORDER BY id DESC LIMIT ?", (token, limit)).fetchall()
    conn.close()
    keys = ["id","ts","index","total_usd","median_usd","sample_size","window_span","verdict"]
    return [dict(zip(keys, r)) for r in rows]

def delta(token: str = "USDC") -> dict:
    """Главный вывод: ИЗМЕНЕНИЕ (R3), а не уровень. Сравниваем с предыдущим."""
    h = history(token, limit=2)
    if len(h) < 2:
        return {"status": "нужна история", "have": len(h),
                "note": "первый замер ещё не с чем сравнить — дельта появится после второго"}
    cur, prev = h[0], h[1]
    d = cur["index"] - prev["index"]
    dv = (cur["total_usd"] - prev["total_usd"])
    return {
        "status": "ok",
        "from_ts": prev["ts"], "to_ts": cur["ts"],
        "index_before": prev["index"], "index_now": cur["index"],
        "index_delta": round(d, 1),
        "direction": "растёт" if d > 0.5 else ("падает" if d < -0.5 else "плато"),
        "volume_delta_usd": round(dv, 2),
        "sample_now": cur["sample_size"], "sample_before": prev["sample_size"],
    }

def series(token: str = "USDC", limit: int = 60) -> list[float]:
    return [r["index"] for r in reversed(history(token, limit))]

if __name__ == "__main__":
    import sys
    if "--delta" in sys.argv:
        print(json.dumps(delta(), ensure_ascii=False, indent=2))
    elif "--series" in sys.argv:
        print(json.dumps(series(), indent=2))
    else:
        for r in history(limit=20):
            print(f"{r['ts'][:19]}  idx={r['index']:>5}  ${r['total_usd']:>14,.0f}  n={r['sample_size']:>4}  {r['verdict']}")