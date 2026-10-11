#!/usr/bin/env python3
"""
VEEDER · Telegram-бот
═══════════════════════════════════════════════════════════════════
Продукт: ежедневный отчёт «Индекс реальности платежей» по крипте.
Монетизация: Telegram Stars (мгновенно, без KYC, без сети-латентности).

Логика:
  /start    → тизер с бесплатной частью отчёта
  /report   → полный отчёт (только для подписчиков)
  /subscribe→ оплата Stars (aiogram 3.x, XTR)
  /my       → статус подписки
  /help     → помощь

Запуск:  python3 bot.py          (поллинг)
═══════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import asyncio, logging, sys
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, CallbackQuery,
)

from indexer import scan, render, render_reference, load_env

# ── конфиг ──────────────────────────────────────────────────────────────
ENV = load_env()
TOKEN  = ENV.get("VEEDER_BOT_TOKEN") or ENV.get("TG_CRYPTO") or ENV.get("TG_DEFIONEDEV_BOT")
STAR_PRICE = int(ENV.get("VEEDER_STARS", "25"))   # ~цена подписки на месяц, в Stars
DB_FILE = Path(__file__).parent / ".cache" / "subs.json"

# Прямое соединение с api.telegram.org из этой сети висит (DNS отдаёт IPv6).
# Рабочий маршрут — Tor SOCKS5, как у остальных ботов проекта.
PROXY = ENV.get("VEEDER_PROXY") or ENV.get("TG_PROXY") or None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("veeder")

if not TOKEN:
    sys.exit("❌ Нет токена бота. Добавь VEEDER_BOT_TOKEN=... в ~/.env")

def _proxy_obj():
    """Сессия aiogram с SOCKS-прокси, если задан.

    В .env прокси записан как socks5h:// (DNS через прокси), но aiohttp_socks
    такую схему не понимает. Удалённое резолвирование обеспечивает rdns=True,
    который aiogram проставляет сам — поэтому приводим схему к socks5.
    """
    if not PROXY: return None
    url = PROXY.replace("socks5h://", "socks5://", 1)
    try:
        from aiogram.client.session.aiohttp import AiohttpSession
        s = AiohttpSession(proxy=url)
        return s
    except Exception as e:
        log.warning("прокси %s не применился (%s) — прямое соединение", url, e)
        return None

# ── простая «БД» подписчиков (JSON) ─────────────────────────────────────
def _load_subs() -> dict:
    if DB_FILE.exists():
        import json
        try: return json.loads(DB_FILE.read_text(encoding="utf-8"))
        except Exception: return {}
    return {}

def _save_subs(d: dict) -> None:
    import json
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    DB_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

SUBS = _load_subs()      # {user_id: {"until": epoch, "name": str}}

def is_active(uid: int) -> bool:
    import time
    rec = SUBS.get(str(uid))
    return bool(rec and rec.get("until", 0) > time.time())

# ── тексты ──────────────────────────────────────────────────────────────
TEASER = (
    "<b>VEEDER</b> · индекс реальности платежей в крипте\n\n"
    "Каждый день считаю по публичным данным блокчейна: сколько платежей,\n"
    "сколько за ними денег, и каков разрыв между числом операций и ценностью.\n\n"
    "Зачем: x402 провёл <b>154 млн</b> транзакций агентов —\n"
    "а расчёт за неделю всего <b>$41 800</b>.\n"
    "Кто платит $0.00027 за транзакцию? Есть ли за этим экономика?\n"
    "Ответ — измеряю, а не пересказываю.\n\n"
    "<b>Бесплатно</b> — тизер индекса.\n"
    "<b>Подписка</b> — полный ежедневный отчёт с разбором, за Telegram Stars.\n\n"
    "Нажми /report, если подписка активна."
)

HELP = (
    "<b>VEEDER — что это</b>\n"
    "Ежедневный аналитический отчёт по платежам в крипте.\n"
    "Считаю сам по публичным данным Etherscan, никакой воды и пересказов.\n\n"
    "<b>Команды</b>\n"
    "/start — тизер\n"
    "/report — полный отчёт (подписка)\n"
    "/subscribe — оформить подписку\n"
    "/my — статус подписки\n"
    "/help — эта справка\n\n"
    "<i>Оплата — Telegram Stars. Это мгновенно и без банковских карт.</i>"
)

def sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"★ Подписка · {STAR_PRICE} Stars", callback_data="buy")],
        [InlineKeyboardButton(text="★ Что даёт подписка", callback_data="why")],
    ])

# ── хендлеры ───────────────────────────────────────────────────────────
def build_dp() -> Dispatcher:
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def cmd_start(m: Message):
        await m.answer(TEASER, parse_mode=ParseMode.HTML, reply_markup=sub_kb())

    @dp.message(Command("help"))
    @dp.message(Command("subscribe", "sub"))
    async def cmd_help(m: Message):
        await m.answer(HELP, parse_mode=ParseMode.HTML)

    @dp.message(Command("subscribe"))
    async def cmd_sub(m: Message):
        await m.answer(
            f"★ Подписка VEEDER — <b>{STAR_PRICE} Stars</b>.\n"
            f"Что внутри: полный ежедневный отчёт, разбор динамики индекса,\n"
            f"отслеживание сигнала «экономика появляется / не появляется».",
            parse_mode=ParseMode.HTML, reply_markup=sub_kb(),
        )

    @dp.message(Command("report"))
    async def cmd_report(m: Message):
        rep = await asyncio.to_thread(scan)
        if "error" in rep:
            await m.answer(f"⚠️ Индекс временно недоступен: {rep['error']}")
            return
        if not is_active(m.from_user.id):
            teaser = render(rep)
            # бесплатно — только первые строки индекса
            cut = teaser.split("Профиль переводов")[0]
            await m.answer(
                cut + "\n\n🔒 <b>Полный отчёт — по подписке.</b>\n"
                     "Оформить: /subscribe",
                parse_mode=ParseMode.HTML, reply_markup=sub_kb(),
            )
            return
        await m.answer(render(rep) + render_reference(rep), parse_mode=ParseMode.HTML)

    @dp.message(Command("my"))
    async def cmd_my(m: Message):
        import time
        rec = SUBS.get(str(m.from_user.id))
        if rec and rec.get("until", 0) > time.time():
            left = int((rec["until"] - time.time()) / 86400) + 1
            await m.answer(f"✅ Подписка активна. Осталось ~{left} дн.", parse_mode=ParseMode.HTML)
        else:
            await m.answer("❌ Подписки нет.", parse_mode=ParseMode.HTML,
                           reply_markup=sub_kb())

    @dp.callback_query(F.data == "buy")
    async def cb_buy(cb: CallbackQuery):
        await cb.message.answer_invoice(
            title="VEEDER · подписка",
            description=(f"Ежедневный отчёт «Индекс реальности платежей в крипте».\n"
                         f"Подписка на 30 дней. Полный разбор с данными блокчейна."),
            payload="veeder_sub_30d",
            provider_token="",           # Stars: пусто для XTR
            currency="XTR",
            prices=[LabeledPrice(label=f"{STAR_PRICE} Stars", amount=STAR_PRICE)],
        )

    @dp.callback_query(F.data == "why")
    async def cb_why(cb: CallbackQuery):
        await cb.message.answer(
            "<b>Что даёт подписка</b>\n\n"
            "🔓 <b>Бесплатно</b>: тизер — сам индекс и вердикт.\n"
            "🔐 <b>Подписка</b>:\n"
            "  • полный отчёт с разбором профиля платежей;\n"
            "  • динамика индекса день ко дню;\n"
            "  • отслеживание сигнала: появилась ли реальная агентная экономика\n"
            "    или x402 навсегда останется на $41 800 в неделю.\n\n"
            f"<b>Цена: {STAR_PRICE} Stars</b> (≈ Telegram-эквивалент небольшой подписки).\n"
            "Оплата мгновенная, без карт.",
            parse_mode=ParseMode.HTML,
        )

    @dp.pre_checkout_query()
    async def pre_checkout(q):
        await q.answer(ok=True)

    @dp.message(F.successful_payment)
    async def on_paid(m: Message):
        import time
        uid = str(m.from_user.id)
        SUBS[uid] = {"until": time.time() + 30 * 86400,
                     "name": m.from_user.first_name or ""}
        _save_subs(SUBS)
        log.info("оплата: user=%s stars=%s", uid, m.successful_payment.total_amount)
        await m.answer("✅ Подписка на 30 дней активирована.\nПолный отчёт: /report",
                       parse_mode=ParseMode.HTML)

    return dp

# ── запуск ──────────────────────────────────────────────────────────────
async def main():
    session = _proxy_obj()
    kw = {"session": session} if session else {}
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), **kw)
    dp = build_dp()
    log.info("VEEDER запущен (Stars=%s, прокси=%s, подписчиков=%s)",
             STAR_PRICE, PROXY or "прямой", len(SUBS))
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("остановлен")