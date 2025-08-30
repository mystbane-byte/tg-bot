# bot_fixed_html.py
import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ContentType, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import ReplyKeyboardBuilder
import aiosqlite

# === Настройка логирования ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Загрузка переменных окружения ===
load_dotenv()
TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID_ENV = os.getenv("ADMIN_CHAT_ID")
SUPPORT_USER_ID_ENV = os.getenv("SUPPORT_USER_ID")
DISCORD_LINK = os.getenv("DISCORD_LINK") or "https://discord.gg/your-link"
SERVER_IP = os.getenv("SERVER_IP") or "0.0.0.0"
SERVER_IP2 = os.getenv("SERVER_IP2") or "0.0.0.0"

# Валидация обязательных переменных
if not TOKEN:
    logger.critical("TOKEN не установлен в .env — прерывание запуска.")
    raise SystemExit("TOKEN is required")

try:
    ADMIN_CHAT_ID = int(ADMIN_CHAT_ID_ENV) if ADMIN_CHAT_ID_ENV else None
except ValueError:
    logger.exception("ADMIN_CHAT_ID не является целым числом.")
    ADMIN_CHAT_ID = None

try:
    SUPPORT_USER_ID = int(SUPPORT_USER_ID_ENV) if SUPPORT_USER_ID_ENV else None
except ValueError:
    logger.exception("SUPPORT_USER_ID не является целым числом.")
    SUPPORT_USER_ID = None

# === Инициализация бота и диспетчера ===
bot = Bot(token=TOKEN)
dp = Dispatcher()

# === Хранилище для скриншотов ===
caption_storage: Dict[int, Dict[str, Any]] = {}

# === Утилиты ===
def is_private_chat(message: Message) -> bool:
    return message.chat.type == "private"

# === Клавиатуры ===
def get_main_keyboard() -> ReplyKeyboardBuilder:
    kb = ReplyKeyboardBuilder()
    kb.button(text="🚀 Start")
    kb.button(text="💎 Купить проходку")
    kb.button(text="📞 Поддержка")
    kb.button(text="📖 FAQ")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=False)

def get_buy_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Реквизиты для оплаты", callback_data="payment_details")],
            [InlineKeyboardButton(text="🤝 Техподдержка", url=f"tg://user?id={SUPPORT_USER_ID or 0}")]
        ]
    )

def get_start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Купить проходку", callback_data="buy_pass")],
            [InlineKeyboardButton(text="📞 Поддержка", callback_data="support")],
            [InlineKeyboardButton(text="📖 FAQ", callback_data="faq")]
        ]
    )

def history_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔄 Обновить список", callback_data="refresh_history")]]
    )

# === Тексты сообщений ===
WELCOME_TEXT = (
    "👋 Привет! Это бот продажи проходки на сервер <b>SculkED</b> (Minecraft Java 1.21.8).\n\n"
    "💳 <i>Способы оплаты:</i>\n"
    "• Перевод на карту (Сбер/Тинькофф)\n\n"
    "⏳ Обычно отвечаем в течение дня.\n\n"
    "<i>После оплаты отправьте скриншот чека/перевода и ваш ник Minecraft для добавления в whitelist.</i>"
)

PRODUCT_TEXT = (
    "💎 <b>Проходка на сервер SculkED</b>\n\n"
    "Актуальные цены:\n\n"
    "1) 2,5 месяца — <b>250₽</b>\n\n"
    "2) 1 сезон (1 год) — <b>450₽</b>\n\n"
    "3) 2 сезона (2 года) — <b>550₽</b>\n\n"
    "⚠️ <i>После оплаты деньги не возвращаем.</i>\n"
    "Выберите способ оплаты:"
)

PAYMENT_DETAILS_TEXT = (
    "💳 <b>Реквизиты для оплаты:</b>\n\n"
    "• <b>Сбербанк:</b> <code>2202 2032 7696 2364</code>\n"
    "• <b>Тинькофф:</b> <code>2200 7009 4965 0401</code>\n\n"
    "После оплаты отправьте скриншот чека с ником Minecraft в этот чат.\n\n"
    "<i>P.S. Скриншот автоматически отправляется администраторам.</i>"
)

SUPPORT_TEXT = (
    "📞 <b>Связь с командой:</b>\n\n"
    f"• 🤝 Техподдержка - технические вопросы\n"
    f'  <a href="tg://user?id={SUPPORT_USER_ID or 0}">Написать в поддержку</a>\n\n'
    "⏳ Обычно отвечаем в течение дня."
)

FAQ_TEXT = (
    "📖 *FAQ — Часто задаваемые вопросы*\n\n"
    "❓ <i>Где посмотреть свой ник в Minecraft?</i>\n"
    "👉 Ник отображается в лаунчере (справа от кнопки <i>играть</i>).\n"
    "Или альтернативный вариант: зайдите на официальный сайт майнкрафта: https://www.minecraft.net/ru-ru\n"
    "Нажмите на учетную запись (справа сверху) -> профиль -> все игры -> изменить имя профиля.\n\n"
    "❓ <i>Что делать после оплаты?</i>\n"
    "👉 Отправьте скриншот чека/перевода и ваш ник в Minecraft прямо в чат с ботом.\n\n"
    "❓ <i>Когда меня добавят в whitelist?</i>\n"
    "👉 Обычно в течение суток после подтверждения оплаты администратором.\n\n"
    "❓ <i>Можно ли вернуть деньги?</i>\n"
    "👉 ⚠️ Нет, возврат средств не предусмотрен.\n\n"
    "❓ <i>Не могу зайти на сервер. Что делать?</i>\n"
    "👉 Проверьте, что используете правильный IP.\n\n"
    "❓ <i>Нужен лицензионный майнкрафт или можно зайти через TLauncher?</i>\n"
    "👉 Да! Вы можете играть и без лицензии.\n\n"
    "❓ <i>Какая версия майнкрафта?</i>\n"
    "👉 1.21.8.\n\n"
    "❓ <i>Можно зайти через Bedrock?</i>\n"
    "👉 Нет! Только через Java Edition.\n\n"
    "Есть другие вопросы — напишите в поддержку."
)

# === База данных ===
DB_PATH = "payments.db"

async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    nick TEXT,
                    status TEXT,
                    time TEXT
                )
            """)
            await db.commit()
    except Exception:
        logger.exception("Ошибка при инициализации базы данных")

async def save_payment_history(user_id: int, username: Optional[str], nick: Optional[str], status: str):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO payments (user_id, username, nick, status, time) VALUES (?, ?, ?, ?, ?)",
                (user_id, username or "", nick or "", status, now)
            )
            await db.commit()
    except Exception:
        logger.exception("Ошибка при сохранении в историю платежей")

async def fetch_history(limit: int = 20):
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, username, nick, status, time FROM payments ORDER BY time DESC LIMIT ?",
                (limit,)
            )
            rows = await cursor.fetchall()
            await cursor.close()
            return rows
    except Exception:
        logger.exception("Ошибка при получении истории")
        return []

def format_history(rows):
    if not rows:
        return "📂 Заявок пока нет."
    text = "📂 Последние заявки:\n\n"
    for user_id, username, nick, status, time in rows:
        status_emoji = {"approved": "✅", "rejected": "❌", "retry_requested": "📝"}.get(status, "ℹ️")
        text += (
            f"{status_emoji} ID: <code>{user_id}</code>, user: @{username or ''}, "
            f"Ник: <b>{nick or ''}</b>\nСтатус: <i>{status}</i> | Время: {time}\n\n"
        )
    return text

# === Хендлеры ===
@dp.message(F.text.in_(["/start", "🚀 Start"]))
async def start_cmd(message: Message):
    if not is_private_chat(message):
        return
    await message.answer(WELCOME_TEXT, reply_markup=get_start_keyboard(), parse_mode=ParseMode.HTML)

@dp.message(F.text == "💎 Купить проходку")
async def buy_pass(message: Message):
    if not is_private_chat(message):
        return
    await message.answer(PRODUCT_TEXT, reply_markup=get_buy_keyboard(), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "buy_pass")
async def inline_buy_pass(callback: CallbackQuery):
    await callback.message.answer(PRODUCT_TEXT, reply_markup=get_buy_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "payment_details")
async def inline_payment_details(callback: CallbackQuery):
    await callback.message.answer(PAYMENT_DETAILS_TEXT, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "support")
async def inline_support(callback: CallbackQuery):
    await callback.message.answer(SUPPORT_TEXT, disable_web_page_preview=True, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.callback_query(F.data == "faq")
async def inline_faq(callback: CallbackQuery):
    await callback.message.answer(FAQ_TEXT, disable_web_page_preview=True, parse_mode=ParseMode.HTML)
    await callback.answer()

@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    if not is_private_chat(message):
        return
    await message.answer(SUPPORT_TEXT, disable_web_page_preview=True, parse_mode=ParseMode.HTML)

@dp.message(F.text == "📖 FAQ")
async def faq(message: Message):
    if not is_private_chat(message):
        return
    await message.answer(FAQ_TEXT, disable_web_page_preview=True, parse_mode=ParseMode.HTML)

# === Обработка скриншотов ===
@dp.message(F.content_type == ContentType.PHOTO)
async def handle_screenshot(message: Message):
    if not is_private_chat(message):
        return
    if not message.caption or not message.caption.strip():
        await message.answer("❌ Укажите ник в подписи к скриншоту.")
        return
    nick_raw = message.caption.strip()
    username = message.from_user.username or message.from_user.first_name or ""
    base_caption = f"Скрин от @{username} (ник: {nick_raw})"
    try:
        sent = await bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=message.photo[-1].file_id,
            caption=base_caption
        )
        msg_id = sent.message_id
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"approve_{msg_id}"),
                InlineKeyboardButton(text="❌ Отклонить оплату", callback_data=f"reject_{msg_id}"),
                InlineKeyboardButton(text="📝 Запросить повторное фото", callback_data=f"retry_{msg_id}")
            ]]
        )
        caption_storage[msg_id] = {
            "caption": base_caption,
            "user_id": message.from_user.id,
            "username": username,
            "nick": nick_raw
        }
        await bot.edit_message_reply_markup(chat_id=sent.chat.id, message_id=sent.message_id, reply_markup=kb)
        await message.answer("✅ Скрин отправлен админам для проверки оплаты.")
    except Exception:
        logger.exception("Ошибка отправки скрина в админ-группу")
        await message.answer("❌ Не удалось отправить скрин в админ-группу.")

# === Админские callback-обработчики ===
@dp.callback_query(lambda c: c.data and any(c.data.startswith(p) for p in ["approve_", "reject_", "retry_"]))
async def admin_actions(callback: CallbackQuery):
    action, msg_id_str = callback.data.split("_", 1)
    try:
        msg_id = int(msg_id_str)
    except ValueError:
        await callback.answer("❌ Неверный ID сообщения")
        return
    info = caption_storage.get(msg_id)
    if not info:
        await callback.answer("❌ Информация о пользователе не найдена.")
        return
    user_id = info["user_id"]
    username = info.get("username") or ""
    nick = info.get("nick") or ""
    caption = info.get("caption", "")
    allowed_admins = [ADMIN_CHAT_ID] if ADMIN_CHAT_ID else []
    if SUPPORT_USER_ID:
        allowed_admins.append(SUPPORT_USER_ID)
    if callback.from_user.id not in allowed_admins:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    status_text = ""
    db_status = ""
    try:
        if action == "approve":
            status_text = "✅ Оплата подтверждена"
            db_status = "approved"
            await save_payment_history(user_id, username, nick, db_status)
            await bot.send_message(user_id, f"✅ Оплата подтверждена!\n\n🌐 Discord: {DISCORD_LINK}\n\n🖥️ IP: {SERVER_IP}\n🖥️ IP других стран: {SERVER_IP2}")
        elif action == "reject":
            status_text = "❌ Оплата отклонена"
            db_status = "rejected"
            await save_payment_history(user_id, username, nick, db_status)
            await bot.send_message(user_id, "❌ Оплата отклонена. Свяжитесь с поддержкой.")
        elif action == "retry":
            status_text = "📝 Запрошено новое фото"
            db_status = "retry_requested"
            await save_payment_history(user_id, username, nick, db_status)
            await bot.send_message(user_id, "📝 Пожалуйста, отправьте новое фото чека с вашим ником.")
    except Exception:
        logger.exception("Ошибка при уведомлении пользователя или сохранении статуса")
    new_caption = f"{caption}\n\n{status_text}"
    try:
        await bot.edit_message_caption(chat_id=callback.message.chat.id, message_id=callback.message.message_id, caption=new_caption)
    except Exception:
        logger.exception("Не удалось изменить caption в админском сообщении")
    await callback.answer("✅ Действие выполнено")

@dp.callback_query(F.data == "refresh_history")
async def refresh_history(callback: CallbackQuery):
    allowed_user_ids = [uid for uid in (SUPPORT_USER_ID, ADMIN_CHAT_ID) if uid]
    if callback.from_user.id not in allowed_user_ids:
        await callback.answer("❌ Нет доступа", show_alert=True)
        return
    rows = await fetch_history()
    new_text = format_history(rows)
    try:
        current_text = callback.message.text or ""
        if new_text != current_text:
            await bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=callback.message.message_id,
                text=new_text,
                reply_markup=history_keyboard(),
                parse_mode=ParseMode.HTML
            )
            await callback.answer("✅ Список обновлен")
        else:
            await callback.answer("ℹ️ Список уже актуален")
    except Exception:
        logger.exception("Ошибка обновления истории")
        await callback.answer("❌ Не удалось обновить список", show_alert=True)

# === Команды админа (работают только через хендлеры, без подсказок) ===
# === Команды админа (только в группе, без подсказок) ===
@dp.message(F.text == "/history")
async def admin_history(message: Message):
    # Работает только в админской группе
    if message.chat.id != ADMIN_CHAT_ID:
        return
    rows = await fetch_history()
    await message.answer(format_history(rows), reply_markup=history_keyboard(), parse_mode=ParseMode.HTML)


@dp.message(F.text == "/clear_history")
async def admin_clear_history(message: Message):
    # Работает только в админской группе
    if message.chat.id != ADMIN_CHAT_ID:
        return
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM payments")
            await db.commit()
        await message.answer("✅ История платежей очищена.")
    except Exception:
        logger.exception("Ошибка при очистке истории")
        await message.answer("❌ Не удалось очистить историю.")


# === Очистка подсказок команд Telegram при запуске ===
async def clear_commands():
    try:
        await bot.delete_my_commands()
        logger.info("✅ Команды Telegram очищены, подсказки не отображаются")
    except Exception:
        logger.exception("Не удалось очистить команды Telegram")


# === Обработка неизвестных сообщений ===
@dp.message()
async def unknown_message(message: Message):
    if not is_private_chat(message):
        return
    await message.answer("🤖 Я не понял ваше сообщение. Используйте кнопки меню:", reply_markup=get_main_keyboard())

# === Инициализация бота ===
async def init_bot():
    await init_db()
    logger.info("Бот готов к работе")

async def main():
    await init_bot()
    await clear_commands()
    logger.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        logger.info("Бот остановлен")

