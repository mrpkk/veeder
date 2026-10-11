#!/usr/bin/env python3
"""
VEEDER · Индекс реальности платежей
═══════════════════════════════════════════════════════════════════
Считает по публичным данным Etherscan: сколько платежей, сколько денег,
и каков разрыв между числом операций и реальной ценностью.

ЭТО ТОТ САМЫЙ РАЗРЫВ, который я нашёл в исследовании:
  x402 — 154 млн транзакций агентов
  расчёт за неделю — около $41 800 (−93% г/г)
Вопрос: настоящая это экономика или надутая метрика? Бот отвечает каждый день.

ЧЕСТНОСТЬ: признаки «агентности» здесь эвристические, не точные.
Мы не знаем, какие адреса принадлежат агентам. Мы измеряем ПРОФИЛЬ
платежей и сравниваем с базовой линией. Никаких причинных выводов.
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import os, json, time, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from statistics import median

# ── конфиг ──────────────────────────────────────────────────────────────
def load_env(path: str | Path = Path.home() / ".env") -> dict:
    env: dict[str, str] = {}
    if Path(path).exists():
        for line in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

ENV = load_env()
ETHERSCAN_KEY = ENV.get("ETHERSCAN_API_KEY", "")
CACHE_FILE = Path(__file__).parent / ".cache" / "last_scan.json"
CACHE_TTL = 15 * 60          # не чаще раза в 15 минут

# ── сеть ────────────────────────────────────────────────────────────────
Etherscan = "https://api.etherscan.io/v2/api"
USDC   = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"   # Ethereum mainnet
USDT   = "0xdAC17F958D2ee523a2206206994597C13D831ec7"
STABLES = {"USDC": USDC, "USDT": USDT}

def etherscan(params: dict, chainid: int = 1) -> dict:
    p = dict(params); p["apikey"] = ETHERSCAN_KEY
    url = f"{Etherscan}?chainid={chainid}&" + urllib.parse.urlencode(p)
    req = urllib.request.Request(url, headers={"User-Agent": "veeder/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def fetch_transfers(contract: str, offset: int = 1000) -> list[dict]:
    """Последние N переводов токена."""
    out, page = [], 1
    while len(out) < offset and page <= 10:
        r = etherscan({
            "module": "account", "action": "tokentx",
            "contractaddress": contract, "page": page, "offset": 100,
            "start": 0, "sort": "desc",
        })
        if r.get("status") != "1" or not isinstance(r.get("result"), list) or not r["result"]:
            break
        out.extend(r["result"])
        page += 1
        time.sleep(0.22)                     # не долбить лимиты
    return out[:offset]

# ── метрики ─────────────────────────────────────────────────────────────
def pct(a: float, b: float) -> float:
    return (a / b * 100) if b else 0.0

def analyse(transfers: list[dict]) -> dict:
    """Профиль платежей и индекс реальности."""
    if not transfers:
        return {"error": "нет данных"}

    vals = [int(t["value"]) / 1e6 for t in transfers]          # в долларах
    senders = {t["from"].lower() for t in transfers}
    receivers = {t["to"].lower() for t in transfers}

    n = len(vals)
    total = sum(vals)
    med = median(vals)

    sub1   = sum(1 for v in vals if v < 1)
    sub5   = sum(1 for v in vals if v < 5)
    sub50  = sum(1 for v in vals if v < 50)
    big    = sum(1 for v in vals if v >= 50)
    round_ = sum(1 for v in vals if abs(v - round(v)) < 0.001)   # «круглые» суммы
    repeat = sum(1 for v in vals if v in (1, 2, 5, 10, 25, 50, 100))

    # ── ИНДЕКС РЕАЛЬНОСТИ ────────────────────────────────────────────
    # Идея: массовые микроплатежи с «круглыми» повторяющимися суммами и высокой
    # долей «шумных» отправителей — признак автоматизации без экономики.
    # Настоящая экономика = крупные, неповторяющиеся, «человеческие» суммы.
    # Значение 0…100. Ниже 35 → «экономики нет, есть трафик».
    noise_share = (sub50 / n * 100) * 0.35 + (repeat / n * 100) * 0.25 \
                + (round_ / n * 100) * 0.20 + max(0.0, (50 - pct(n - len(senders), n))) * 0.20
    reality = max(0.0, min(100.0, 100.0 - noise_share))

    verdict = (
        "ЭКОНОМИКИ НЕТ · трафик есть, денег нет" if reality < 35 else
        "ЗАРОЖДАЕТСЯ · первые признаки реальной ценности" if reality < 60 else
        "ЕСТЬ · переводы несут экономическую нагрузку"
    )

    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "window": {"from": min(t["timeStamp"] for t in transfers),
                   "to":   max(t["timeStamp"] for t in transfers)},
        "counts": {
            "transfers": n, "senders": len(senders), "receivers": len(receivers),
            "sub_1usd": sub1, "sub_5usd": sub5, "sub_50usd": sub50, "ge_50usd": big,
            "round_amounts": round_, "repeat_amounts": repeat,
        },
        "value": {
            "total_usd": round(total, 2), "median_usd": round(med, 4),
            "avg_usd": round(total / n, 4), "max_usd": round(max(vals), 2),
        },
        "shares_pct": {
            "sub_1": round(pct(sub1, n), 1), "sub_5": round(pct(sub5, n), 1),
            "sub_50": round(pct(sub50, n), 1), "round": round(pct(round_, n), 1),
        },
        "reality_index": round(reality, 1),
        "verdict": verdict,
        # эталон, ради которого всё затевалось (x402, 2026)
        "reference": {"x402_transactions": 154_000_000, "x402_weekly_settlement_usd": 41_800,
                      "implied_usd_per_tx": 0.00027,
                      "note": "154 млн транзакций на $41 800 в неделю — либо покупают воздух, либо метрика надута"},
    }

# ── публичный вход ──────────────────────────────────────────────────────
def scan(tokens: tuple[str, ...] = ("USDC",), force: bool = False) -> dict:
    """Главная функция. Возвращает отчёт; кэширует 15 минут."""
    if not ETHERSCAN_KEY:
        return {"error": "нет ETHERSCAN_API_KEY в ~/.env"}

    if not force and CACHE_FILE.exists():
        age = time.time() - CACHE_FILE.stat().st_mtime
        if age < CACHE_TTL:
            return json.loads(CACHE_FILE.read_text(encoding="utf-8"))

    all_tx: list[dict] = []
    for t in tokens:
        try:
            all_tx.extend(fetch_transfers(STABLES[t]))
        except Exception:
            continue
    if not all_tx:
        return {"error": "Etherscan не отдал данные"}

    rep = analyse(all_tx)
    rep["tokens"] = list(tokens)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")
    return rep

# ── текстовый отчёт ─────────────────────────────────────────────────────
def render(rep: dict) -> str:
    if "error" in rep:
        return f"⚠️ {rep['error']}"
    c, v, s = rep["counts"], rep["value"], rep["shares_pct"]
    bar = "█" * int(rep["reality_index"] / 5) + "░" * (20 - int(rep["reality_index"] / 5))
    return (
        f"<b>VEEDER · индекс реальности</b>\n\n"
        f"<code>{bar}</code>  <b>{rep['reality_index']}</b>/100\n"
        f"<b>{rep['verdict']}</b>\n\n"
        f"<b>Окно:</b> {c['transfers']} переводов {rep.get('tokens',['USDC'])[0]}, {c['senders']} отправителей\n"
        f"<b>Объём:</b> ${v['total_usd']:,.0f} · медиана ${v['median_usd']}\n\n"
        f"<b>Профиль переводов</b>\n"
        f"  &lt; $1 ........ {s['sub_1']}%\n"
        f"  &lt; $5 ........ {s['sub_5']}%\n"
        f"  &lt; $50 ....... {s['sub_50']}%\n"
        f"  ≥ $50 ........ {c['ge_50usd']} шт\n"
        f"  «круглые» суммы .. {s['round']}%\n\n"
        f"<i>Это профиль переводов {rep.get('tokens',['USDC'])[0]} в сети Ethereum — DeFi, биржи, расчёты.\n"
        f"Об индексе нагрузки — читать так: доля мелких и «круглых» платежей.\n"
        f"Признаки агентности эвристические, не причинно-следственные.</i>"
    )

def render_reference(rep: dict) -> str:
    r = rep.get("reference", {})
    if not r: return ""
    return (
        f"\n\n<b>Отдельный кейс: платежи агентов (x402)</b>\n"
        f"Наш индекс меряет переводы {rep.get('tokens',['USDC'])[0]} в Ethereum — это <b>другая популяция</b>.\n"
        f"Ниже — задокументированный крайний случай, ради которого всё затевалось:\n"
        f"x402: {r['x402_transactions']:,} транзакций агентов\n"
        f"расчёт за неделю: ${r['x402_weekly_settlement_usd']:,}\n"
        f"→ ${r['implied_usd_per_tx']:.5f} на транзакцию\n"
        f"<i>{r['note']}</i>"
    )

if __name__ == "__main__":
    import sys
    rep = scan(force="--force" in sys.argv)
    print(render(rep))
    print(render_reference(rep))