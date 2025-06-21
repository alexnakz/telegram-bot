import os
from aiogram import Bot, Dispatcher, types
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# Проверяем, что переменные существуют
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

if not BOT_TOKEN:
    raise ValueError("❌ Ошибка: BOT_TOKEN не задан в .env!")
if not ADMIN_ID:
    raise ValueError("❌ Ошибка: ADMIN_ID не задан в .env!")

try:
    ADMIN_ID = int(ADMIN_ID)  # Преобразуем в число
except ValueError:
    raise ValueError("⚠️ ADMIN_ID должен быть числом (например, 123456789)!")

# Инициализируем бота
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Пример обработчика команды /start
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer("Привет! Бот работает.")

if __name__ == "__main__":
    from aiogram import executor
    executor.start_polling(dp)
