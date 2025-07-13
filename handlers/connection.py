from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from utils.admin_utils import check_admin_level, get_mikrotik_list

router = Router()

# Состояния FSM для выбора микротика
class SelectMikrotik(StatesGroup):
    waiting_for_mikrotik = State()

# Хранилище текущего выбранного микротика для каждого пользователя
user_mikrotik = {}

def get_connection_keyboard():
    """Создает клавиатуру для выбора микротика"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔄 Выбрать микротик")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        persistent=True
    )
    return keyboard

@router.message(Command("connect"))
async def connect_command(message: types.Message):
    """Обработчик команды выбора микротика"""
    admin_level = check_admin_level(message.from_user.id)
    
    if admin_level == 0:
        return await message.reply("Доступ запрещён. Эта команда доступна только администраторам.")
    
    await send_mikrotiks_selection(message, 1)

@router.message(lambda message: message.text == "🔄 Выбрать микротик")
async def select_mikrotik_command(message: types.Message):
    """Обработчик кнопки выбора микротика"""
    admin_level = check_admin_level(message.from_user.id)
    
    if admin_level == 0:
        return await message.reply("Доступ запрещён.")
    
    await send_mikrotiks_selection(message, 1)

async def send_mikrotiks_selection(message: types.Message, page: int = 1):
    """Отправляет список микротиков для выбора с пагинацией"""
    # Получаем список доступных микротиков
    mikrotiks = get_mikrotik_list(message.from_user.id)
    
    if not mikrotiks:
        return await message.reply("Нет доступных микротиков.")
    
    # Параметры пагинации
    items_per_page = 8  # 8 микротиков на страницу
    total_pages = (len(mikrotiks) + items_per_page - 1) // items_per_page
    
    # Проверяем корректность страницы
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    # Вычисляем срез для текущей страницы
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(mikrotiks))
    current_mikrotiks = mikrotiks[start_idx:end_idx]
    
    # Создаем кнопки для текущей страницы (по 2 в ряд для компактности)
    buttons = []
    row = []
    for i, mikrotik in enumerate(current_mikrotiks):
        row.append(InlineKeyboardButton(text=mikrotik['name'], callback_data=f"connect_mikrotik:{mikrotik['id']}"))
        
        # Добавляем по 2 кнопки в ряд
        if len(row) == 2 or i == len(current_mikrotiks) - 1:
            buttons.append(row)
            row = []
    
    # Добавляем кнопки навигации, только если страниц больше одной
    if total_pages > 1:
        nav_buttons = []
        
        # Кнопка "Предыдущая"
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"mikrotiks_select_page:{page-1}"))
        
        # Информация о текущей странице
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"mikrotiks_select_page:{page+1}"))
        
        buttons.append(nav_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    page_info = f" (страница {page}/{total_pages})" if total_pages > 1 else ""
    current_mikrotik = get_current_mikrotik(message.from_user.id)
    current_info = ""
    
    if current_mikrotik:
        # Найдем название текущего микротика
        current_name = "Неизвестный"
        for m in mikrotiks:
            if m['id'] == current_mikrotik:
                current_name = m['name']
                break
        current_info = f"\n🔗 Текущий: {current_name}"
    
    await message.reply(
        f"Выберите микротик для подключения{page_info}:{current_info}\n"
        f"Всего доступно: {len(mikrotiks)}",
        reply_markup=keyboard
    )

# Обработчик для пагинации выбора микротиков
@router.callback_query(F.data.startswith("mikrotiks_select_page:"))
async def mikrotiks_select_page_callback(callback: CallbackQuery):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level == 0:
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    # Получаем номер страницы
    page = int(callback.data.split(":", 1)[1])
    
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
    # Создаем новое сообщение с новой страницей
    # Получаем список доступных микротиков
    mikrotiks = get_mikrotik_list(callback.from_user.id)
    
    if not mikrotiks:
        await callback.answer("Нет доступных микротиков", show_alert=True)
        return
    
    # Параметры пагинации
    items_per_page = 8  # 8 микротиков на страницу
    total_pages = (len(mikrotiks) + items_per_page - 1) // items_per_page
    
    # Проверяем корректность страницы
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    # Вычисляем срез для текущей страницы
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(mikrotiks))
    current_mikrotiks = mikrotiks[start_idx:end_idx]
    
    # Создаем кнопки для текущей страницы (по 2 в ряд для компактности)
    buttons = []
    row = []
    for i, mikrotik in enumerate(current_mikrotiks):
        row.append(InlineKeyboardButton(text=mikrotik['name'], callback_data=f"connect_mikrotik:{mikrotik['id']}"))
        
        # Добавляем по 2 кнопки в ряд
        if len(row) == 2 or i == len(current_mikrotiks) - 1:
            buttons.append(row)
            row = []
    
    # Добавляем кнопки навигации, только если страниц больше одной
    if total_pages > 1:
        nav_buttons = []
        
        # Кнопка "Предыдущая"
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"mikrotiks_select_page:{page-1}"))
        
        # Информация о текущей странице
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"mikrotiks_select_page:{page+1}"))
        
        buttons.append(nav_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    page_info = f" (страница {page}/{total_pages})" if total_pages > 1 else ""
    current_mikrotik = get_current_mikrotik(callback.from_user.id)
    current_info = ""
    
    if current_mikrotik:
        # Найдем название текущего микротика
        current_name = "Неизвестный"
        for m in mikrotiks:
            if m['id'] == current_mikrotik:
                current_name = m['name']
                break
        current_info = f"\n🔗 Текущий: {current_name}"
    
    # Отправляем новое сообщение
    await callback.message.answer(
        f"Выберите микротик для подключения{page_info}:{current_info}\n"
        f"Всего доступно: {len(mikrotiks)}",
        reply_markup=keyboard
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("connect_mikrotik:"))
async def connect_mikrotik_callback(callback: CallbackQuery):
    """Обработчик выбора микротика"""
    mikrotik_id = callback.data.split(":", 1)[1]
    user_id = callback.from_user.id
    
    # Проверяем доступ к микротику
    mikrotiks = get_mikrotik_list(user_id)
    mikrotik_names = {m['id']: m['name'] for m in mikrotiks}
    
    if mikrotik_id not in mikrotik_names:
        return await callback.answer("У вас нет доступа к этому микротику.", show_alert=True)
    
    # Сохраняем выбранный микротик для пользователя
    user_mikrotik[user_id] = mikrotik_id
    
    await callback.message.edit_text(f"✅ Вы подключились к микротику: {mikrotik_names[mikrotik_id]}")
    
    # Отправляем сообщение с основным меню
    from handlers.vpn import get_main_menu
    await callback.message.answer(
        f"🔗 Текущий микротик: {mikrotik_names[mikrotik_id]}\n"
        f"Теперь вы можете управлять VPN на этом устройстве.",
        reply_markup=get_main_menu(user_id)
    )
    
    await callback.answer(f"Подключен к {mikrotik_names[mikrotik_id]}")

def get_current_mikrotik(user_id):
    """Возвращает ID текущего выбранного микротика для пользователя"""
    return user_mikrotik.get(user_id)