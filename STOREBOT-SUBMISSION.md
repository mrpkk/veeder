# Подача veeder в StoreBot

Дата: 13.10.2026. StoreBot проверен, отвечает 200, форма живая.

## Что это за каталог

<https://storebot.me> — каталог Telegram-ботов, «The Bot Directory». Для
нас это самое прямое попадание из всех найденных площадок: `veeder` уже
работает и уже принимает оплату Stars, не хватает только витрины.

Форма подачи: <https://storebot.me/add-bot> — требует имя, почту, заголовок,
картинку и описание.

**Почта — твоя.** Публиковать от твоего имени я не буду.

## Готово

| Что | Где |
|---|---|
| Иконка 512×512 | `/media/Sruti/iamthat/work/crypto/veeder/assets/veeder-icon.png` |
| Иконка 128×128 | `/media/Sruti/iamthat/work/crypto/veeder/assets/veeder-icon-128.png` |

## Что вписать в форму

### Title
```
VEEDER — index of real payments
```

### Bot Description
```
A daily measurement of whether agent payments are real, computed from public
blockchain data rather than repeated from news.

x402 has processed 154 million agent transactions. Weekly settlement is about
$41,800 — roughly $0.00027 per transaction. Stablecoin float is $33 trillion.

Who pays $0.00027? Is there an economy behind that number, or is the metric
inflated? The bot measures and publishes the answer daily.

It counts payments, money behind them, and the gap between the number of
operations and their value.

Free: the index and the verdict.
Subscription: the full daily report, with a breakdown of the payment profile
and a running signal on whether real agent economics is appearing.

Paid with Telegram Stars — no card, no KYC, no wallet.

Honesty note: the markers of agent-ness are heuristic, not exact. We do not
know which addresses belong to agents, so we measure the payment profile and
compare it against a baseline. No causal claims are made.
```

### Bot Commands
```
/start — the index and the current verdict
/report — full daily report (subscribers)
/subscribe — start a subscription via Telegram Stars
/my — subscription status
/help — commands
```

### Upload Bot Image
`assets/veeder-icon.png`

### Status
`Online` — бот работает, отвечает на все команды, polling идёт.

## Почему это может принести деньги

StoreBot — каталог ботов, а не витрина разработчиков. Трафик идёт от
людей, которые **ищут готового бота**, а не от тех, кто строит агентов.
Это ближе всего к нашей ситуации: покупатель не читает README, он ищет
работающий инструмент и хочет им пользоваться.

При этом каталог не переполнен аналитическими ботами — конкуренция в
этой нише единицы.

## Честно о состоянии бота

| | |
|---|---|
| Бот работает | да, polling, все команды отвечают |
| Оплата Stars | код написан и проверен |
| Замеров в индексе | **2** |
| Подписчиков | **0** |
| Заработано | **0** |

Бот новый и подписчиков не имеет. Каталог даст первые показы, но
рассчитывать, что они сразу превратятся в оплату, нельзя: это вход в
воронку, а не выручка.
