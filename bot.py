import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
from datetime import datetime

# Настройки
from dotenv import load_dotenv
import os

load_dotenv()  # Загружает переменные из .env файла

TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

# База данных заказов
orders_db = {}

# ===== КЛАВИАТУРЫ =====
def get_main_keyboard(user_id: int):
    """Главное меню с кнопками"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Список заказов", callback_data="list_orders")
    builder.button(text="🧾 Мои заказы", callback_data="my_orders")
    if user_id == ADMIN_ID:
        builder.button(text="📊 Статистика", callback_data="show_stats")
        builder.button(text="➕ Добавить заказ", callback_data="add_order_prompt")
    builder.adjust(1)
    return builder.as_markup()

def get_orders_keyboard(order_type: str = "active"):
    """Клавиатура со списком заказов"""
    builder = InlineKeyboardBuilder()
    for num, data in orders_db.items():
        if (order_type == "active" and not data['taken']) or \
           (order_type == "taken" and data['taken']):
            builder.button(
                text=f"#{num}: {data['desc'][:15]}...",
                callback_data=f"view_{order_type}_{num}"
            )
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def get_order_actions_keyboard(order_num: str, is_owner: bool):
    """Действия с конкретным заказом"""
    builder = InlineKeyboardBuilder()
    if not orders_db[order_num]['taken']:
        builder.button(text="✅ Взять заказ", callback_data=f"take_{order_num}")
    elif is_owner:
        builder.button(text="❌ Отменить", callback_data=f"cancel_{order_num}")
    builder.button(text="🔙 Назад", callback_data="back_to_orders")
    builder.adjust(1)
    return builder.as_markup()

# ===== КОМАНДЫ =====
@dp.message(Command("start"))
async def start(message: Message):
    await show_main_menu(message)

async def show_main_menu(message):
    """Показать главное меню (работает с Message и CallbackQuery)"""
    if isinstance(message, CallbackQuery):
        msg = message.message
        edit_method = msg.edit_text
        user_id = message.from_user.id
    else:
        msg = message
        edit_method = msg.answer
        user_id = message.from_user.id

    await edit_method(
        "Главное меню:",
        reply_markup=get_main_keyboard(user_id)
    )

# ===== ОБРАБОТКА КНОПОК =====
@dp.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    await show_main_menu(callback)

@dp.callback_query(F.data == "list_orders")
async def list_orders(callback: CallbackQuery):
    # Создаем клавиатуру
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для каждого доступного заказа
    active_orders = False
    for num, data in orders_db.items():
        if not data['taken']:
            builder.button(
                text=f"#{num}: {data['desc'][:15]}...",
                callback_data=f"view_active_{num}"
            )
            active_orders = True
    
    # Если нет активных заказов
    if not active_orders:
        builder.button(text="🔄 Проверить снова", callback_data="list_orders")
    
    # Общие кнопки навигации
    builder.button(text="🧾 Мои заказы", callback_data="my_orders")
    builder.button(text="🔙 Главное меню", callback_data="main_menu")
    builder.adjust(1)
    
    # Формируем текст сообщения
    text = "Доступные заказы:" if active_orders else "Нет доступных заказов"
    
    # Отправляем/обновляем сообщение
    try:
        await callback.message.edit_text(
            text,
            reply_markup=builder.as_markup()
        )
    except:
        await callback.message.answer(
            text,
            reply_markup=builder.as_markup()
        )
    
    await callback.answer()

@dp.callback_query(F.data == "my_orders")
async def my_orders(callback: CallbackQuery):
    try:
        # Получаем список заказов пользователя
        user_orders = [
            (num, data) for num, data in orders_db.items() 
            if data['taken'] and data['taken_by'] == callback.from_user.username
        ]
        
        if not user_orders:
            # Если заказов нет
            keyboard = InlineKeyboardBuilder()
            keyboard.button(text="📋 Список заказов", callback_data="list_orders")
            keyboard.button(text="🔄 Проверить снова", callback_data="my_orders")
            keyboard.button(text="🔙 Главное меню", callback_data="main_menu")
            keyboard.adjust(1)
            
            await callback.message.edit_text(
                "У вас пока нет взятых заказов",
                reply_markup=keyboard.as_markup()
            )
        else:
            # Если заказы есть
            builder = InlineKeyboardBuilder()
            for num, data in user_orders:
                builder.button(
                    text=f"#{num}: {data['desc'][:15]}...",
                    callback_data=f"view_taken_{num}"
                )
            
            builder.button(text="🔙 Назад", callback_data="main_menu")
            builder.adjust(1)
            
            await callback.message.edit_text(
                "Ваши заказы:",
                reply_markup=builder.as_markup()
            )
            
    except Exception as e:
        logging.error(f"Ошибка в my_orders: {e}")
        await callback.answer("Произошла ошибка, попробуйте позже")
    finally:
        await callback.answer()


@dp.callback_query(F.data.startswith("view_"))
async def view_order(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        if len(parts) != 3:
            await callback.answer("Неверный формат запроса!")
            return
            
        order_type, order_num = parts[1], parts[2]
        order = orders_db.get(order_num)
        
        
        if not order:
            await callback.answer("Заказ не найден!")
            return
        
        is_owner = order['taken'] and order['taken_by'] == callback.from_user.username
        
        text = (
            f"📋 <b>Заказ #{order_num}</b>\n\n"
            f"<b>Описание:</b>\n{order['desc']}\n\n"
            f"<b>Статус:</b> {'✅ Взято' if order['taken'] else '🟢 Доступно'}\n"
        )
        
        if order['taken']:
            text += f"👤 <b>Исполнитель:</b> @{order['taken_by']}\n"
            text += f"⏰ <b>Время:</b> {order['taken_time']}\n"
        
        await callback.message.edit_text(
            text,
            reply_markup=get_order_actions_keyboard(order_num, is_owner),
            parse_mode="HTML"
        )
    except Exception as e:
        logging.error(f"Error in view_order: {e}")
        await callback.answer("Произошла ошибка, попробуйте позже")

@dp.callback_query(F.data.startswith("take_"))
async def take_order(callback: CallbackQuery):
    order_num = callback.data.split("_")[1]
    order = orders_db.get(order_num)
    
    if not order:
        await callback.answer("Заказ не найден!")
        return
    
    if order['taken']:
        await callback.answer("Этот заказ уже взят!")
        return
    
    # Обновляем данные заказа
    order.update({
        'taken': True,
        'taken_by': callback.from_user.username,
        'taken_time': datetime.now().strftime("%d.%m.%Y %H:%M")
    })
    
    # Создаем клавиатуру с кнопками навигации
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🧾 Мои заказы", callback_data="my_orders")
    keyboard.button(text="📋 Список заказов", callback_data="list_orders")
    keyboard.adjust(1)
    
    # Обновляем сообщение с сохранением клавиатуры
    await callback.message.edit_text(
        f"✅ Вы успешно взяли заказ #{order_num}!\n\n"
        f"<b>Описание:</b>\n{order['desc']}\n\n"
        f"Вы можете просмотреть его в разделе 'Мои заказы'",
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML"
    )
    
    # Уведомление админу (отдельное сообщение)
    await bot.send_message(
        ADMIN_ID,
        f"📢 Заказ #{order_num} взят!\n"
        f"👤 Пользователь: @{callback.from_user.username}\n"
        f"⏰ Время: {order['taken_time']}\n"
        f"📝 Описание: {order['desc']}"
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("cancel_"))
async def cancel_order(callback: CallbackQuery):
    order_num = callback.data.split("_")[1]
    order = orders_db.get(order_num)
    
    if not order or not order['taken']:
        await callback.answer("Заказ не найден или уже отменен!")
        return
    
    if order['taken_by'] != callback.from_user.username:
        await callback.answer("Вы не можете отменить этот заказ!")
        return
    
    # Сохраняем информацию для уведомления
    order_desc = order['desc']
    username = order['taken_by']
    
    # Обновляем статус заказа
    order.update({
        'taken': False,
        'taken_by': None,
        'taken_time': None
    })
    
    # Создаем клавиатуру для возврата
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 К моим заказам", callback_data="my_orders")
    keyboard.button(text="📋 К списку заказов", callback_data="list_orders")
    keyboard.adjust(1)
    
    # Обновляем сообщение с сохранением клавиатуры
    await callback.message.edit_text(
        f"❌ Вы отменили заказ #{order_num}\n\n"
        f"<b>Описание:</b>\n{order_desc}\n\n"
        f"Теперь этот заказ снова доступен для взятия.",
        reply_markup=keyboard.as_markup(),
        parse_mode="HTML"
    )
    
    # Уведомление админу
    await bot.send_message(
        ADMIN_ID,
        f"⚠️ Заказ #{order_num} отменен!\n"
        f"👤 Пользователь: @{username}\n"
        f"📝 Описание: {order_desc}"
    )
    await callback.answer()

@dp.callback_query(F.data == "back_to_orders")
async def back_to_orders(callback: CallbackQuery):
    # Определяем, откуда пришел пользователь (из "Мои заказы" или "Список заказов")
    if "Ваши заказы" in callback.message.text:
        await my_orders(callback)
    else:
        await list_orders(callback)
@dp.callback_query(F.data == "show_stats")
async def show_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Только для администратора!")
        return
    
    # Создаем списки для активных и выполненных заказов
    active_orders = []
    taken_orders = []
    
    # Заполняем списки данными
    for num, data in orders_db.items():
        if not data['taken']:
            active_orders.append(f"🔹 #{num}: {data['desc']}")
        else:
            taken_info = [
                f"✅ #{num}: {data['desc']}",
                f"👤 @{data['taken_by']}",
                f"⏰ {data['taken_time']}",
                ""  # Пустая строка для разделения
            ]
            taken_orders.extend(taken_info)
    
    # Формируем текст сообщения
    message_lines = [
        "📊 <b>Статистика заказов</b>",
        "",
        "🔄 <b>Активные заказы:</b>",
    ]
    
    # Добавляем активные заказы или сообщение об их отсутствии
    if not active_orders:
        message_lines.append("Нет активных заказов")
    else:
        message_lines.extend(active_orders)
    
    message_lines.extend([
        "",
        "✔️ <b>Взятые заказы:</b>"
    ])
    
    # Добавляем выполненные заказы или сообщение об их отсутствии
    if not taken_orders:
        message_lines.append("Нет взятых заказов")
    else:
        message_lines.extend(taken_orders)
    
    # Создаем клавиатуру для возврата
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data="main_menu")
    
    # Отправляем сообщение
    await callback.message.edit_text(
        "\n".join(message_lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )

@dp.callback_query(F.data == "add_order_prompt")
async def add_order_prompt(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("Только для администратора!")
        return
    
    await callback.message.edit_text(
        "Введите заказ в формате:\n"
        "<code>Номер: Описание</code>\n"
        "Пример: <code>1: Доставить пиццу</code>",
        parse_mode="HTML"
    )

@dp.message(F.text.regexp(r"^\d+\s*:.+"))
async def add_order(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    try:
        num, desc = message.text.split(":", 1)
        orders_db[num.strip()] = {
            'desc': desc.strip(),
            'taken': False,
            'taken_by': None,
            'taken_time': None
        }
        await message.answer(
            f"✅ Заказ #{num.strip()} добавлен!",
            reply_markup=get_main_keyboard(message.from_user.id)
        )
    except:
        await message.answer("❌ Ошибка. Формат: Номер: Описание")

# ===== ЗАПУСК БОТА =====
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен! Для остановки нажмите Ctrl+C")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот остановлен")
