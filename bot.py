import logging
import asyncio
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, ContentType, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import ReplyKeyboardBuilder

# === Загрузка .env ===
load_dotenv()

TOKEN = os.getenv("TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
SUPPORT_USER_ID = int(os.getenv("SUPPORT_USER_ID"))
DISCORD_LINK = os.getenv("DISCORD_LINK")
SERVER_IP = os.getenv("SERVER_IP")
SERVER_IP2 = os.getenv("SERVER_IP2")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

# === Клавиатуры ===
def get_main_keyboard():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🚀 Start")
    kb.button(text="💎 Купить проходку")
    kb.button(text="📞 Поддержка")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

def get_buy_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Реквизиты для оплаты", callback_data="payment_details")],
            [InlineKeyboardButton(text="🤝 Техподдержка", url=f"tg://user?id={SUPPORT_USER_ID}")]
        ]
    )

def get_start_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💎 Купить проходку", callback_data="buy_pass")],
            [InlineKeyboardButton(text="🤝 Техподдержка", url=f"tg://user?id={SUPPORT_USER_ID}")]
        ]
    )

# === Тексты ===
WELCOME_TEXT = (
    "👋 Привет! Это бот продажи проходки на сервер **SculkED** (Minecraft Java).\n\n"
    "💳 *Способы оплаты:*\n"
    "• Перевод на карту (Сбер/Тинькофф)\n\n"
    
    "⏳ Обычно отвечаем в течение дня.\n\n"
    
    "После оплаты отправьте скриншот чека/перевода и Ваш никнейм Minecraft для добавления в whitelist."
)

PRODUCT_TEXT = (
    "💎 *Проходка на сервер SculkED*\n\n"
    "Актуальные цены:\n\n"
    "1) На два с половиной месяца — 250₽\n"
    "2) На один сезон (1 год) — 450₽\n"
    "3) (Проходка +) на 2 сезона (2 года) — 550₽\n\n"
    "Выберите способ оплаты:\n\n"
    "⚠️ После оплаты деньги не возвращаем."
)

PAYMENT_DETAILS_TEXT = (
    "💳 *Реквизиты для оплаты:*\n\n"
    "• **Сбербанк:** `2202 2032 7696 2364`\n"
    "• **Тинькофф:** `2200 7009 4965 0401`\n\n"
    
    "После оплаты отправьте: скриншот чека/перевода вместе с ником Minecraft в этот чат с ботом.\n\n"
    "P.S. Он автоматически отправляется администраторам."
)

SUPPORT_TEXT = (
    "📞 *Связь с командой:*\n\n"
    f"• 🤝 Техподдержка - технические вопросы\n"
    f"  [Написать в поддержку](tg://user?id={SUPPORT_USER_ID})\n\n"
    "⏳ Обычно отвечаем в течение дня."
)

# === Проверка приватного чата ===
def is_private_chat(message: Message):
    return message.chat.type == "private"

# === /start ===
@dp.message(F.text.in_(["/start", "🚀 Start"]))
async def start_cmd(message: Message):
    if not is_private_chat(message):
        return
    await message.answer(WELCOME_TEXT, reply_markup=get_start_keyboard())
    await message.answer("👇 Или используйте кнопки ниже для навигации:", reply_markup=get_main_keyboard())

# === Кнопки "Купить проходку" и "Поддержка" ===
@dp.message(F.text == "💎 Купить проходку")
async def buy_pass(message: Message):
    if not is_private_chat(message):
        return
    await message.answer(PRODUCT_TEXT, reply_markup=get_buy_keyboard())

@dp.message(F.text == "📞 Поддержка")
async def support(message: Message):
    if not is_private_chat(message):
        return
    await message.answer(SUPPORT_TEXT)

@dp.callback_query(F.data == "buy_pass")
async def process_buy_pass(callback: CallbackQuery):
    await callback.message.answer(PRODUCT_TEXT, reply_markup=get_buy_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "payment_details")
async def payment_details(callback: CallbackQuery):
    await callback.message.answer(PAYMENT_DETAILS_TEXT)
    await callback.answer()

# === Обработка скриншотов с ником ===
@dp.message(F.content_type == ContentType.PHOTO)
async def handle_screenshot(message: Message):
    if not is_private_chat(message):
        return
    if not message.caption:
        await message.answer("❌ Пожалуйста, укажите ваш ник в подписи к скриншоту.")
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить оплату", callback_data=f"approve_{message.from_user.id}")]
        ]
    )

    try:
        await bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=message.photo[-1].file_id,
            caption=f"Скрин от @{message.from_user.username} (ник: {message.caption})",
            reply_markup=kb
        )
        await message.answer("✅ Скрин отправлен админам для проверки оплаты.\n\nПосле подтверждения оплаты вам отправится Discord и IP сервера.")
    except Exception as e:
        await message.answer("❌ Не удалось отправить скрин в админ-группу. Проверьте настройки ADMIN_CHAT_ID.")
        logging.error(f"Ошибка отправки скрина: {e}")

# === Подтверждение оплаты админом ===
@dp.callback_query(lambda c: c.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    try:
        await bot.send_message(
            chat_id=user_id,
            text=(
                "✅ Оплата подтверждена!\n\n"
                f"🌐 Discord сервер: {DISCORD_LINK}\n\n"
                f"🖥️ IP сервера для России: {SERVER_IP}\n"
                f"🖥️ IP сервера для других стран: {SERVER_IP2}\n\n"
                f"⚠️ В случае неактивности от 2 месяцев, проходка аннулируется.\n"
            )
        )
        await callback.answer("Оплата подтверждена, сообщение отправлено пользователю!")
        await callback.message.edit_caption(
            caption=f"{callback.message.caption}\n\n✅ Оплата подтверждена."
        )
    except Exception as e:
        await callback.answer("❌ Не удалось отправить сообщение пользователю.")
        logging.error(f"Ошибка отправки Discord/IP пользователю: {e}")

# === Любые другие сообщения ===
@dp.message()
async def unknown_message(message: Message):
    if not is_private_chat(message):
        return
    await message.answer(
        "🤖 Я не понял ваше сообщение.\nИспользуйте кнопки меню для навигации:",
        reply_markup=get_main_keyboard()
    )

# === Запуск бота ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

