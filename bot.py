import os
from datetime import datetime, time
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TZ_NAME = os.getenv("TZ", "Europe/Moscow")  # МСК по умолчанию
TZ = ZoneInfo(TZ_NAME)

# ===== РАСПИСАНИЕ + КОНТАКТЫ (МСК) =====
# 0=Пн 1=Вт 2=Ср 3=Чт 4=Пт 5=Сб 6=Вс
SCHEDULE = {
    "Михаил": {
        "tg": "@Phili_M",
        "phone": "+7 967 258 9242",
        "shifts": {
            0: [("11:00", "20:00")],  # Пн
            1: [("11:00", "20:00")],  # Вт
            2: [("11:00", "20:00")],  # Ср
            3: [("08:00", "20:00")],  # Чт
            4: [("08:00", "20:00")],  # Пт
            # Сб/Вс выходные
        },
    },
    "Кирилл": {
        "tg": "@Piala_yuu",
        "phone": "+7 951 174 0727",
        "shifts": {
            0: [("06:00", "15:00")],  # Пн
            1: [("06:00", "15:00")],  # Вт
            2: [("06:00", "15:00")],  # Ср
            5: [("08:00", "18:00")],  # Сб (обновлено: с 9)
            6: [("08:00", "18:00")],  # Вс (обновлено: с 9)
            # Чт/Пт выходные
        },
    },
}
# ======================================

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def is_working_now(person: str, now: datetime):
    """Возвращает (работает_ли, 'до HH:MM' или None)"""
    wd = now.weekday()
    t = now.time()

    shifts_today = SCHEDULE.get(person, {}).get("shifts", {}).get(wd, [])
    for start_s, end_s in shifts_today:
        start = parse_hhmm(start_s)
        end = parse_hhmm(end_s)

        # обычная смена
        if start <= end:
            if start <= t < end:
                return True, end_s
        else:
            # смена через полночь (на будущее)
            if t >= start or t < end:
                return True, end_s

    return False, None


def who_is_working(now: datetime):
    result = []
    for person in SCHEDULE.keys():
        ok, until = is_working_now(person, now)
        if ok and until:
            result.append((person, until))
    return result


def format_day_schedule(wd: int) -> str:
    lines = [f"📅 Расписание на {WEEKDAYS_RU[wd]}:"]
    for person, info in SCHEDULE.items():
        shifts = info.get("shifts", {}).get(wd, [])
        tg = info["tg"]
        phone = info["phone"]

        if not shifts:
            lines.append(f"• {person}: выходной  | {tg}, {phone}")
        else:
            intervals = ", ".join([f"{s}–{e}" for s, e in shifts])
            lines.append(f"• {person}: {intervals}  | {tg}, {phone}")

    return "\n".join(lines)


def format_week_schedule() -> str:
    lines = ["📆 Расписание на неделю:"]
    for wd in range(7):
        lines.append(f"\n{WEEKDAYS_RU[wd]}:")
        for person, info in SCHEDULE.items():
            shifts = info.get("shifts", {}).get(wd, [])
            if not shifts:
                lines.append(f"  • {person}: выходной")
            else:
                intervals = ", ".join([f"{s}–{e}" for s, e in shifts])
                lines.append(f"  • {person}: {intervals}")
    return "\n".join(lines)


def main_menu():
    kb = InlineKeyboardBuilder()

    # апгрейд: всегда можно вернуться в меню
    kb.button(text="🏠 Меню", callback_data="menu")

    kb.button(text="👥 Кто работает сейчас", callback_data="now")
    kb.button(text="📅 Расписание на сегодня", callback_data="today")
    kb.button(text="📆 Расписание на неделю", callback_data="week")

    for person in SCHEDULE.keys():
        kb.button(text=f"📞 {person}", callback_data=f"person:{person}")

    kb.adjust(1, 2, 2)  # 1 в первой строке, потом по 2
    return kb.as_markup()


bot = Bot(BOT_TOKEN)
dp = Dispatcher()


def menu_text() -> str:
    now = datetime.now(TZ)
    return (
        "Выбери действие 👇\n"
        f"Сейчас: {now.strftime('%Y-%m-%d %H:%M')} ({TZ_NAME})\n\n"
        "Если открыл чат заново — просто напиши любое сообщение, и меню появится."
    )


@dp.message(F.text.in_({"/start", "/menu"}))
async def start(message: Message):
    await message.answer(menu_text(), reply_markup=main_menu())


# ✅ Апгрейд: если “повторно зашёл в бот” — напиши что угодно, меню появится
@dp.message()
async def any_message_show_menu(message: Message):
    # не мешаем командам: они уже обработаны выше
    await message.answer(menu_text(), reply_markup=main_menu())


@dp.callback_query(F.data == "menu")
async def back_to_menu(call: CallbackQuery):
    await call.message.answer(menu_text(), reply_markup=main_menu())
    await call.answer()


@dp.callback_query(F.data == "now")
async def who_now(call: CallbackQuery):
    now = datetime.now(TZ)
    workers = who_is_working(now)

    if not workers:
        text = f"Сейчас никто не работает.\nВремя: {now.strftime('%Y-%m-%d %H:%M')} ({TZ_NAME})"
    else:
        lines = [f"Сейчас работают (время {now.strftime('%H:%M')}):"]
        for name, until in workers:
            tg = SCHEDULE[name]["tg"]
            phone = SCHEDULE[name]["phone"]
            lines.append(f"• {name} — до {until}\n  Контакты: {tg}, {phone}")
        text = "\n".join(lines)

    await call.message.answer(text)
    await call.answer()


@dp.callback_query(F.data == "today")
async def schedule_today(call: CallbackQuery):
    now = datetime.now(TZ)
    wd = now.weekday()
    text = format_day_schedule(wd) + f"\n\nСейчас: {now.strftime('%Y-%m-%d %H:%M')} ({TZ_NAME})"
    await call.message.answer(text)
    await call.answer()


@dp.callback_query(F.data == "week")
async def schedule_week(call: CallbackQuery):
    now = datetime.now(TZ)
    text = format_week_schedule() + f"\n\nСейчас: {now.strftime('%Y-%m-%d %H:%M')} ({TZ_NAME})"
    await call.message.answer(text)
    await call.answer()


@dp.callback_query(F.data.startswith("person:"))
async def person(call: CallbackQuery):
    name = call.data.split(":", 1)[1]
    now = datetime.now(TZ)
    ok, until = is_working_now(name, now)

    tg = SCHEDULE[name]["tg"]
    phone = SCHEDULE[name]["phone"]

    if ok:
        text = (
            f"✅ {name} сейчас работает (до {until}).\n"
            f"Контакты: {tg}, {phone}\n"
            f"Время: {now.strftime('%Y-%m-%d %H:%M')} ({TZ_NAME})"
        )
    else:
        text = (
            f"❌ {name} сейчас не работает.\n"
            f"Контакты: {tg}, {phone}\n"
            f"Время: {now.strftime('%Y-%m-%d %H:%M')} ({TZ_NAME})"
        )

    await call.message.answer(text)
    await call.answer()


if __name__ == "__main__":
    import asyncio

    if not BOT_TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN. Проверь файл .env рядом с bot.py")

    asyncio.run(dp.start_polling(bot))

