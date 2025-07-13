from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import json
import logging

from utils.admin_utils import (
    check_admin_level, add_mikrotik, upload_openvpn_template,
    add_level2_admin, get_mikrotik_list, delete_mikrotik, delete_admin,
    get_mikrotik_by_id, edit_mikrotik_field, update_admin_name,
    update_admin_mikrotiks, promote_admin_to_level1, demote_admin_to_level2
)

router = Router()

# Создаем логгер
logger = logging.getLogger("vpn_bot")

from utils.admin_utils import (
    check_admin_level, add_mikrotik, upload_openvpn_template,
    add_level2_admin, get_mikrotik_list, delete_mikrotik, delete_admin
)
# Состояния FSM для редактирования микротика
class EditMikrotik(StatesGroup):
    waiting_for_field = State()  # Ожидание выбора поля для редактирования
    waiting_for_name = State()
    waiting_for_host = State()
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_ovpn_profile = State()
    waiting_for_wg_interface = State()
    waiting_for_wg_endpoint = State()
    waiting_for_wg_allowed_ips = State()
# Состояния FSM для добавления микротика
class AddMikrotik(StatesGroup):
    waiting_for_name = State()
    waiting_for_host = State()
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_ovpn_profile = State()
    waiting_for_wg_interface = State()
    waiting_for_wg_endpoint = State()
    waiting_for_wg_allowed_ips = State()

# Состояния FSM для загрузки шаблона OpenVPN
class UploadTemplate(StatesGroup):
    waiting_for_mikrotik = State()
    waiting_for_template = State()

# Состояния FSM для добавления администратора 2-го уровня
class AddAdmin(StatesGroup):
    waiting_for_id = State()
    waiting_for_name = State()
    waiting_for_mikrotiks = State()

# Состояния FSM для редактирования администратора
class EditAdmin(StatesGroup):
    waiting_for_name = State()
    waiting_for_mikrotiks = State()

# Функция для получения клавиатуры администратора 1-го уровня
def get_admin_keyboard():
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🖥️ Управление микротиками"),
                KeyboardButton(text="👨‍💼 Управление администраторами")
            ],
            [
                KeyboardButton(text="📋 OpenVPN Профили"),
                KeyboardButton(text="🔷 WireGuard Профили")
            ],
            [
                KeyboardButton(text="🔄 Активные VPN"),
                KeyboardButton(text="➕ Добавить VPN")
            ],
            [
                KeyboardButton(text="🔄 Выбрать микротик"),
                KeyboardButton(text="🏠 Главное меню")  # Кнопка возврата
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        persistent=True
    )
    return keyboard

# Обработчики для редактирования администраторов
@router.callback_query(F.data.startswith("edit_admin_l1:"))
async def edit_admin_l1_callback(callback: CallbackQuery):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён.", show_alert=True)
    
    admin_id = int(callback.data.split(":", 1)[1])
    
    await callback.message.edit_text(
        f"Редактирование администратора 1-го уровня (ID: {admin_id})\n\n"
        f"Администраторы 1-го уровня имеют полный доступ ко всем функциям.\n"
        f"Вы можете только удалить такого администратора.\n\n"
        f"Хотите понизить этого администратора до 2-го уровня?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↓ Понизить до 2-го уровня", callback_data=f"demote_admin:{admin_id}")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin_list")]
        ])
    )
    
    await callback.answer()

@router.callback_query(F.data.startswith("edit_admin_l2:"))
async def edit_admin_l2_callback(callback: CallbackQuery, state: FSMContext):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён.", show_alert=True)
    
    admin_id = int(callback.data.split(":", 1)[1])
    
    # Получаем данные администратора
    with open('data/admins.json', 'r', encoding='utf-8') as f:
        admins_data = json.load(f)
    
    admin_info = None
    for admin in admins_data["level_2"]:
        if admin["id"] == admin_id:
            admin_info = admin
            break
    
    if not admin_info:
        return await callback.answer("Администратор не найден.", show_alert=True)
    
    # Получаем список микротиков
    mikrotiks = get_mikrotik_list(callback.from_user.id)
    allowed_mikrotiks = admin_info.get("allowed_mikrotiks", [])
    
    # Показываем текущие разрешения
    allowed_names = []
    for mikrotik in mikrotiks:
        if mikrotik["id"] in allowed_mikrotiks:
            allowed_names.append(mikrotik["name"])
    
    await callback.message.edit_text(
        f"Редактирование администратора 2-го уровня:\n"
        f"ID: {admin_id}\n"
        f"Имя: {admin_info.get('name', 'Не указано')}\n"
        f"Доступные микротики: {', '.join(allowed_names) if allowed_names else 'Нет доступа'}\n\n"
        f"Что хотите изменить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Изменить имя", callback_data=f"edit_admin_name:{admin_id}")],
            [InlineKeyboardButton(text="🖥️ Изменить доступ к микротикам", callback_data=f"edit_admin_mikrotiks:{admin_id}")],
            [InlineKeyboardButton(text="↑ Повысить до 1-го уровня", callback_data=f"promote_admin:{admin_id}")],
            [InlineKeyboardButton(text="↩️ Назад", callback_data="back_to_admin_list")]
        ])
    )
    
    await callback.answer()

# Обработчик для изменения имени администратора
@router.callback_query(F.data.startswith("edit_admin_name:"))
async def edit_admin_name_callback(callback: CallbackQuery, state: FSMContext):
    admin_id = int(callback.data.split(":", 1)[1])
    
    await state.update_data(admin_id=admin_id, edit_type="name")
    await callback.message.edit_text("Введите новое имя для администратора:")
    await state.set_state(EditAdmin.waiting_for_name)
    
    await callback.answer()

# Обработчик для изменения доступа к микротикам
@router.callback_query(F.data.startswith("edit_admin_mikrotiks:"))
async def edit_admin_mikrotiks_callback(callback: CallbackQuery, state: FSMContext):
    admin_id = int(callback.data.split(":", 1)[1])
    
    # Получаем данные администратора
    with open('data/admins.json', 'r', encoding='utf-8') as f:
        admins_data = json.load(f)
    
    admin_info = None
    for admin in admins_data["level_2"]:
        if admin["id"] == admin_id:
            admin_info = admin
            break
    
    if not admin_info:
        return await callback.answer("Администратор не найден.", show_alert=True)
    
    # Получаем список микротиков
    mikrotiks = get_mikrotik_list(callback.from_user.id)
    current_mikrotiks = admin_info.get("allowed_mikrotiks", [])
    
    # Создаем inline-клавиатуру для выбора микротиков
    buttons = []
    for mikrotik in mikrotiks:
        is_selected = "✅ " if mikrotik['id'] in current_mikrotiks else "❌ "
        buttons.append([InlineKeyboardButton(
            text=f"{is_selected}{mikrotik['name']}", 
            callback_data=f"toggle_mikrotik:{admin_id}:{mikrotik['id']}"
        )])
    
    # Добавляем кнопку "Готово"
    buttons.append([InlineKeyboardButton(text="✅ Сохранить изменения", callback_data=f"save_admin_mikrotiks:{admin_id}")])
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data=f"edit_admin_l2:{admin_id}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await state.update_data(admin_id=admin_id, selected_mikrotiks=current_mikrotiks[:])  # Копируем текущий список
    
    await callback.message.edit_text(
        f"Настройка доступа к микротикам для администратора {admin_info.get('name')}:\n\n"
        f"✅ - Доступ есть\n"
        f"❌ - Доступа нет\n\n"
        f"Нажмите на микротик, чтобы изменить доступ:",
        reply_markup=keyboard
    )
    
    await callback.answer()

# Обработчик для переключения доступа к микротику
@router.callback_query(F.data.startswith("toggle_mikrotik:"))
async def toggle_mikrotik_callback(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":", 2)
    admin_id = int(parts[1])
    mikrotik_id = parts[2]
    
    # Получаем текущие выбранные микротики из состояния
    data = await state.get_data()
    selected_mikrotiks = data.get("selected_mikrotiks", [])
    
    # Переключаем доступ к микротику
    if mikrotik_id in selected_mikrotiks:
        selected_mikrotiks.remove(mikrotik_id)
    else:
        selected_mikrotiks.append(mikrotik_id)
    
    # Обновляем состояние
    await state.update_data(selected_mikrotiks=selected_mikrotiks)
    
    # Обновляем клавиатуру
    mikrotiks = get_mikrotik_list(callback.from_user.id)
    buttons = []
    for mikrotik in mikrotiks:
        is_selected = "✅ " if mikrotik['id'] in selected_mikrotiks else "❌ "
        buttons.append([InlineKeyboardButton(
            text=f"{is_selected}{mikrotik['name']}", 
            callback_data=f"toggle_mikrotik:{admin_id}:{mikrotik['id']}"
        )])
    
    buttons.append([InlineKeyboardButton(text="✅ Сохранить изменения", callback_data=f"save_admin_mikrotiks:{admin_id}")])
    buttons.append([InlineKeyboardButton(text="↩️ Назад", callback_data=f"edit_admin_l2:{admin_id}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    # Получаем имя админа для отображения
    with open('data/admins.json', 'r', encoding='utf-8') as f:
        admins_data = json.load(f)
    
    admin_name = "Неизвестный"
    for admin in admins_data["level_2"]:
        if admin["id"] == admin_id:
            admin_name = admin.get("name", "Неизвестный")
            break
    
    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer(f"Доступ к микротику {'добавлен' if mikrotik_id in selected_mikrotiks else 'удален'}")

# Остальные обработчики
@router.callback_query(F.data.startswith("save_admin_mikrotiks:"))
async def save_admin_mikrotiks_callback(callback: CallbackQuery, state: FSMContext):
    admin_id = int(callback.data.split(":", 1)[1])
    
    # Получаем выбранные микротики из состояния
    data = await state.get_data()
    selected_mikrotiks = data.get("selected_mikrotiks", [])
    
    # Сохраняем изменения
    success, message = update_admin_mikrotiks(admin_id, selected_mikrotiks, callback.from_user.id)
    
    await callback.message.edit_text(message)
    await state.clear()
    await callback.answer()

@router.callback_query(F.data.startswith("promote_admin:"))
async def promote_admin_callback(callback: CallbackQuery):
    admin_id = int(callback.data.split(":", 1)[1])
    
    success, message = promote_admin_to_level1(admin_id, callback.from_user.id)
    
    await callback.message.edit_text(message)
    await callback.answer()

@router.callback_query(F.data.startswith("demote_admin:"))
async def demote_admin_callback(callback: CallbackQuery, state: FSMContext):
    admin_id = int(callback.data.split(":", 1)[1])
    
    await state.update_data(admin_id=admin_id, edit_type="demote")
    await callback.message.edit_text("Введите имя для понижаемого администратора:")
    await state.set_state(EditAdmin.waiting_for_name)
    
    await callback.answer()

@router.callback_query(F.data == "back_to_admin_list")
async def back_to_admin_list_callback(callback: CallbackQuery):
    # Повторно вызываем функцию отображения списка админов
    await send_admins_list(callback.message, 1)
    await callback.answer()

# Обработчики состояний FSM
@router.message(EditAdmin.waiting_for_name)
async def process_edit_admin_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    admin_id = data.get("admin_id")
    edit_type = data.get("edit_type")
    
    if edit_type == "name":
        success, result = update_admin_name(admin_id, message.text, message.from_user.id)
    elif edit_type == "demote":
        success, result = demote_admin_to_level2(admin_id, message.text, message.from_user.id)
    
    await message.reply(result)
    await state.clear()
    # Возвращаем к главному меню
    from handlers.vpn import get_main_menu
    await message.answer(
        "Можете продолжить работу с ботом:",
        reply_markup=get_main_menu(message.from_user.id)
    )

# Обработчик команды /admin
@router.message(Command("admin"))
async def admin_command(message: types.Message):
    admin_level = check_admin_level(message.from_user.id)
    
    if admin_level != 1:
        return await message.reply("Доступ запрещён. Эта команда доступна только администраторам 1-го уровня.")
    
    await message.reply(
        "Панель управления администратора 1-го уровня",
        reply_markup=get_admin_keyboard()
    )
# обработчик для кнопки редактирования микротика
@router.callback_query(F.data.startswith("edit_mikrotik:"))
async def edit_mikrotik_callback(callback: CallbackQuery):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён.", show_alert=True)
    
    mikrotik_id = callback.data.split(":", 1)[1]
    
    # Получаем данные о микротике
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return await callback.answer("Микротик не найден.", show_alert=True)
    
    # Создаем клавиатуру для выбора поля для редактирования
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Название", callback_data=f"edit_field:{mikrotik_id}:name")],
        [InlineKeyboardButton(text="Хост API", callback_data=f"edit_field:{mikrotik_id}:host")],
        [InlineKeyboardButton(text="Имя пользователя", callback_data=f"edit_field:{mikrotik_id}:username")],
        [InlineKeyboardButton(text="Пароль", callback_data=f"edit_field:{mikrotik_id}:password")],
        [InlineKeyboardButton(text="Профиль OpenVPN", callback_data=f"edit_field:{mikrotik_id}:ovpn_profile")],
        [InlineKeyboardButton(text="Интерфейс WireGuard", callback_data=f"edit_field:{mikrotik_id}:wg_interface")],
        [InlineKeyboardButton(text="Endpoint WireGuard", callback_data=f"edit_field:{mikrotik_id}:wg_endpoint")],
        [InlineKeyboardButton(text="Разрешенные IP WireGuard", callback_data=f"edit_field:{mikrotik_id}:wg_allowed_ips")],
        [InlineKeyboardButton(text="Отмена", callback_data="cancel_edit")]
    ])
    
    await callback.message.edit_text(
        f"Выберите поле для редактирования микротика '{mikrotik.get('name')}':",
        reply_markup=keyboard
    )
    
    await callback.answer()

# обработчик для выбора поля
@router.callback_query(F.data.startswith("edit_field:"))
async def edit_field_callback(callback: CallbackQuery, state: FSMContext):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён.", show_alert=True)
    
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return await callback.answer("Неверный формат данных", show_alert=True)
    
    mikrotik_id = parts[1]
    field = parts[2]
    
    # Сохраняем данные в FSM
    await state.update_data(mikrotik_id=mikrotik_id, field=field)
    
    # Получаем данные о микротике
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return await callback.answer("Микротик не найден.", show_alert=True)
    
    # В зависимости от выбранного поля устанавливаем соответствующее состояние
    field_labels = {
        "name": "название",
        "host": "хост API",
        "username": "имя пользователя",
        "password": "пароль",
        "ovpn_profile": "профиль OpenVPN",
        "wg_interface": "интерфейс WireGuard",
        "wg_endpoint": "endpoint WireGuard",
        "wg_allowed_ips": "разрешенные IP WireGuard"
    }
    
    # Показываем текущее значение
    current_value = ""
    if field in ["name", "host", "username", "password"]:
        current_value = mikrotik.get(field, "")
    elif field == "ovpn_profile":
        current_value = mikrotik.get("openvpn", {}).get("profile", "")
    elif field == "wg_interface":
        current_value = mikrotik.get("wireguard", {}).get("interface_name", "")
    elif field == "wg_endpoint":
        current_value = mikrotik.get("wireguard", {}).get("endpoint", "")
    elif field == "wg_allowed_ips":
        allowed_ips = mikrotik.get("wireguard", {}).get("allowed_ips", [])
        current_value = ", ".join(allowed_ips)
    
    # Устанавливаем состояние и запрашиваем новое значение
    if field == "name":
        await state.set_state(EditMikrotik.waiting_for_name)
    elif field == "host":
        await state.set_state(EditMikrotik.waiting_for_host)
    elif field == "username":
        await state.set_state(EditMikrotik.waiting_for_username)
    elif field == "password":
        await state.set_state(EditMikrotik.waiting_for_password)
    elif field == "ovpn_profile":
        await state.set_state(EditMikrotik.waiting_for_ovpn_profile)
    elif field == "wg_interface":
        await state.set_state(EditMikrotik.waiting_for_wg_interface)
    elif field == "wg_endpoint":
        await state.set_state(EditMikrotik.waiting_for_wg_endpoint)
    elif field == "wg_allowed_ips":
        await state.set_state(EditMikrotik.waiting_for_wg_allowed_ips)
    
    await callback.message.edit_text(
        f"Текущее значение поля '{field_labels.get(field, field)}': {current_value}\n\n"
        f"Введите новое значение:"
    )
    
    await callback.answer()

# обработчики для каждого состояния
@router.callback_query(F.data == "cancel_edit")
async def cancel_edit_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Редактирование отменено.")
    await callback.answer()

# Обработчики состояний для редактирования
@router.message(EditMikrotik.waiting_for_name)
async def process_edit_name(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    # Вызываем функцию редактирования микротика
    success, result = edit_mikrotik_field(mikrotik_id, "name", message.text, message.from_user.id)
    
    await message.reply(result)
    await state.clear()

@router.message(EditMikrotik.waiting_for_host)
async def process_edit_host(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    success, result = edit_mikrotik_field(mikrotik_id, "host", message.text, message.from_user.id)
    
    await message.reply(result)
    await state.clear()

@router.message(EditMikrotik.waiting_for_username)
async def process_edit_username(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    success, result = edit_mikrotik_field(mikrotik_id, "username", message.text, message.from_user.id)
    
    await message.reply(result)
    await state.clear()

@router.message(EditMikrotik.waiting_for_password)
async def process_edit_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    success, result = edit_mikrotik_field(mikrotik_id, "password", message.text, message.from_user.id)
    
    await message.reply(result)
    await state.clear()

@router.message(EditMikrotik.waiting_for_ovpn_profile)
async def process_edit_ovpn_profile(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    success, result = edit_mikrotik_field(mikrotik_id, "ovpn_profile", message.text, message.from_user.id)
    
    await message.reply(result)
    await state.clear()

@router.message(EditMikrotik.waiting_for_wg_interface)
async def process_edit_wg_interface(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    success, result = edit_mikrotik_field(mikrotik_id, "wg_interface", message.text, message.from_user.id)
    
    await message.reply(result)
    await state.clear()

@router.message(EditMikrotik.waiting_for_wg_endpoint)
async def process_edit_wg_endpoint(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    success, result = edit_mikrotik_field(mikrotik_id, "wg_endpoint", message.text, message.from_user.id)
    
    await message.reply(result)
    await state.clear()

@router.message(EditMikrotik.waiting_for_wg_allowed_ips)
async def process_edit_wg_allowed_ips(message: types.Message, state: FSMContext):
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    # Разбиваем введенные IP-адреса по запятой
    allowed_ips = [ip.strip() for ip in message.text.split(",")]
    
    success, result = edit_mikrotik_field(mikrotik_id, "wg_allowed_ips", allowed_ips, message.from_user.id)
    
    await message.reply(result)
    await state.clear()    

# Обработчик кнопки "Управление микротиками"
@router.message(lambda message: message.text == "🖥️ Управление микротиками")
async def manage_mikrotiks(message: types.Message):
    admin_level = check_admin_level(message.from_user.id)
    
    if admin_level != 1:
        return await message.reply("Доступ запрещён.")
    
    await send_mikrotiks_list(message, 1)

async def send_mikrotiks_list(message: types.Message, page: int = 1):
    """Отправляет список микротиков с пагинацией для управления"""
    mikrotiks = get_mikrotik_list(message.from_user.id)
    
    if not mikrotiks:
        await message.reply("Нет доступных микротиков.")
        return
    
    # Параметры пагинации
    items_per_page = 5  # 5 микротиков на страницу (10 кнопок управления)
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
    
    # Создаем кнопки для текущей страницы
    buttons = []
    for mikrotik in current_mikrotiks:
        row = [
            InlineKeyboardButton(text=f"📝 {mikrotik['name']}", callback_data=f"edit_mikrotik:{mikrotik['id']}"),
            InlineKeyboardButton(text=f"🗑️ {mikrotik['name']}", callback_data=f"delete_mikrotik:{mikrotik['id']}")
        ]
        buttons.append(row)
    
    # Добавляем кнопки навигации, только если страниц больше одной
    if total_pages > 1:
        nav_buttons = []
        
        # Кнопка "Предыдущая"
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"mikrotiks_page:{page-1}"))
        
        # Информация о текущей странице
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"mikrotiks_page:{page+1}"))
        
        buttons.append(nav_buttons)
    
    # Добавляем кнопки управления
    management_buttons = [
        [InlineKeyboardButton(text="➕ Добавить микротик", callback_data="add_mikrotik")],
        [InlineKeyboardButton(text="📤 Загрузить шаблон OpenVPN", callback_data="upload_template")]
    ]
    
    buttons.extend(management_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    page_info = f" (страница {page}/{total_pages})" if total_pages > 1 else ""
    
    await message.reply(
        f"Управление микротиками{page_info}:\n"
        f"📝 - Редактировать микротик\n"
        f"🗑️ - Удалить микротик\n"
        f"Всего микротиков: {len(mikrotiks)}",
        reply_markup=keyboard
    )

# Обработчик callback-запроса для пагинации микротиков
@router.callback_query(F.data.startswith("mikrotiks_page:"))
async def mikrotiks_page_callback(callback: CallbackQuery):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    # Получаем номер страницы
    page = int(callback.data.split(":", 1)[1])
    
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
    # Получаем список микротиков
    mikrotiks = get_mikrotik_list(callback.from_user.id)
    
    if not mikrotiks:
        await callback.answer("Нет доступных микротиков", show_alert=True)
        return
    
    # Параметры пагинации
    items_per_page = 5  # 5 микротиков на страницу (10 кнопок управления)
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
    
    # Создаем кнопки для текущей страницы
    buttons = []
    for mikrotik in current_mikrotiks:
        row = [
            InlineKeyboardButton(text=f"📝 {mikrotik['name']}", callback_data=f"edit_mikrotik:{mikrotik['id']}"),
            InlineKeyboardButton(text=f"🗑️ {mikrotik['name']}", callback_data=f"delete_mikrotik:{mikrotik['id']}")
        ]
        buttons.append(row)
    
    # Добавляем кнопки навигации, только если страниц больше одной
    if total_pages > 1:
        nav_buttons = []
        
        # Кнопка "Предыдущая"
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"mikrotiks_page:{page-1}"))
        
        # Информация о текущей странице
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"mikrotiks_page:{page+1}"))
        
        buttons.append(nav_buttons)
    
    # Добавляем кнопки управления
    management_buttons = [
        [InlineKeyboardButton(text="➕ Добавить микротик", callback_data="add_mikrotik")],
        [InlineKeyboardButton(text="📤 Загрузить шаблон OpenVPN", callback_data="upload_template")]
    ]
    
    buttons.extend(management_buttons)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    page_info = f" (страница {page}/{total_pages})" if total_pages > 1 else ""
    
    # Отправляем новое сообщение
    await callback.message.answer(
        f"Управление микротиками{page_info}:\n"
        f"📝 - Редактировать микротик\n"
        f"🗑️ - Удалить микротик\n"
        f"Всего микротиков: {len(mikrotiks)}",
        reply_markup=keyboard
    )
    
    await callback.answer()

# Обработчик кнопки "Управление администраторами"
@router.message(lambda message: message.text == "👨‍💼 Управление администраторами")
async def manage_admins(message: types.Message):
    admin_level = check_admin_level(message.from_user.id)
    
    if admin_level != 1:
        return await message.reply("Доступ запрещён.")
    
    await send_admins_list(message, 1)

async def send_admins_list(message: types.Message, page: int = 1):
    """Отправляет список администраторов с пагинацией"""
    # Загружаем список администраторов
    with open('data/admins.json', 'r', encoding='utf-8') as f:
        admins_data = json.load(f)
    
    # Создаем общий список всех администраторов
    all_admins = []
    
    # Добавляем админов 1-го уровня
    for admin_id in admins_data["level_1"]:
        if admin_id != message.from_user.id:  # Не показываем текущего администратора
            all_admins.append({
                "id": admin_id,
                "level": 1,
                "name": f"ID: {admin_id}",
                "type": "L1"
            })
    
    # Добавляем админов 2-го уровня
    for admin in admins_data["level_2"]:
        all_admins.append({
            "id": admin["id"],
            "level": 2,
            "name": admin.get("name", f"ID: {admin['id']}"),
            "type": "L2"
        })
    
    if not all_admins:
        await message.answer("Нет администраторов для управления.")
        return
    
    # Параметры пагинации
    items_per_page = 5  # 5 администраторов на страницу
    total_pages = (len(all_admins) + items_per_page - 1) // items_per_page
    
    # Проверяем корректность страницы
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    # Вычисляем срез для текущей страницы
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(all_admins))
    current_admins = all_admins[start_idx:end_idx]
    
    # Создаем кнопки для текущей страницы
    buttons = []
    for admin in current_admins:
        if admin["level"] == 1:
            buttons.append([
                InlineKeyboardButton(text=f"📝 {admin['type']}: {admin['name']}", callback_data=f"edit_admin_l1:{admin['id']}"),
                InlineKeyboardButton(text=f"🗑️ {admin['type']}: {admin['name']}", callback_data=f"delete_admin_l1:{admin['id']}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text=f"📝 {admin['type']}: {admin['name']}", callback_data=f"edit_admin_l2:{admin['id']}"),
                InlineKeyboardButton(text=f"🗑️ {admin['type']}: {admin['name']}", callback_data=f"delete_admin_l2:{admin['id']}")
            ])
    
    # Добавляем кнопки навигации
    if total_pages > 1:
        nav_buttons = []
        
        # Кнопка "Предыдущая"
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admins_page:{page-1}"))
        
        # Информация о текущей странице
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"admins_page:{page+1}"))
        
        buttons.append(nav_buttons)
    
    # Добавляем кнопку для добавления нового администратора
    buttons.append([InlineKeyboardButton(text="➕ Добавить администратора", callback_data="add_admin")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    page_info = f" (страница {page}/{total_pages})" if total_pages > 1 else ""
    
    await message.answer(
        f"Управление администраторами{page_info}:\n"
        f"📝 - Редактировать администратора\n"
        f"🗑️ - Удалить администратора\n"
        f"🔴 L1 - Администраторы 1-го уровня\n"
        f"🔶 L2 - Администраторы 2-го уровня\n"
        f"Всего администраторов: {len(all_admins)}",
        reply_markup=keyboard
    )

# Обработчик для пагинации администраторов
@router.callback_query(F.data.startswith("admins_page:"))
async def admins_page_callback(callback: CallbackQuery):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    # Получаем номер страницы
    page = int(callback.data.split(":", 1)[1])
    
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
    # Отправляем новую страницу
    await send_admins_list(callback.message, page)
    await callback.answer()

async def send_admins_list_internal(message: types.Message, page: int = 1):
    """Внутренняя функция для отправки списка администраторов с пагинацией"""
    # Загружаем список администраторов
    with open('data/admins.json', 'r', encoding='utf-8') as f:
        admins_data = json.load(f)
    
    # Создаем общий список всех администраторов
    all_admins = []
    
    # Добавляем админов 1-го уровня
    for admin_id in admins_data["level_1"]:
        if admin_id != message.from_user.id:  # Не показываем текущего администратора
            all_admins.append({
                "id": admin_id,
                "level": 1,
                "name": f"ID: {admin_id}",
                "type": "L1"
            })
    
    # Добавляем админов 2-го уровня
    for admin in admins_data["level_2"]:
        all_admins.append({
            "id": admin["id"],
            "level": 2,
            "name": admin.get("name", f"ID: {admin['id']}"),
            "type": "L2"
        })
    
    if not all_admins:
        await message.answer("Нет администраторов для управления.")
        return
    
    # Параметры пагинации
    items_per_page = 5  # 5 администраторов на страницу
    total_pages = (len(all_admins) + items_per_page - 1) // items_per_page
    
    # Проверяем корректность страницы
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
    
    # Вычисляем срез для текущей страницы
    start_idx = (page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(all_admins))
    current_admins = all_admins[start_idx:end_idx]
    
    # Создаем кнопки для текущей страницы
    buttons = []
    for admin in current_admins:
        if admin["level"] == 1:
            buttons.append([
                InlineKeyboardButton(text=f"📝 {admin['type']}: {admin['name']}", callback_data=f"edit_admin_l1:{admin['id']}"),
                InlineKeyboardButton(text=f"🗑️ {admin['type']}: {admin['name']}", callback_data=f"delete_admin_l1:{admin['id']}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text=f"📝 {admin['type']}: {admin['name']}", callback_data=f"edit_admin_l2:{admin['id']}"),
                InlineKeyboardButton(text=f"🗑️ {admin['type']}: {admin['name']}", callback_data=f"delete_admin_l2:{admin['id']}")
            ])
    
    # Добавляем кнопки навигации
    if total_pages > 1:
        nav_buttons = []
        
        # Кнопка "Предыдущая"
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"admins_page:{page-1}"))
        
        # Информация о текущей странице
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"admins_page:{page+1}"))
        
        buttons.append(nav_buttons)
    
    # Добавляем кнопку для добавления нового администратора
    buttons.append([InlineKeyboardButton(text="➕ Добавить администратора", callback_data="add_admin")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    page_info = f" (страница {page}/{total_pages})" if total_pages > 1 else ""
    
    await message.answer(
        f"Управление администраторами{page_info}:\n"
        f"📝 - Редактировать администратора\n"
        f"🗑️ - Удалить администратора\n"
        f"🔴 L1 - Администраторы 1-го уровня\n"
        f"🔶 L2 - Администраторы 2-го уровня\n"
        f"Всего администраторов: {len(all_admins)}",
        reply_markup=keyboard
    )

# Обработчик callback-запроса для добавления микротика
@router.callback_query(F.data == "add_mikrotik")
async def add_mikrotik_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён.", show_alert=True)
    
    await callback.message.reply("Введите название микротика:")
    await state.set_state(AddMikrotik.waiting_for_name)
    await callback.answer()

# Обработчик callback-запроса для удаления микротика
@router.callback_query(F.data.startswith("delete_mikrotik:"))
async def delete_mikrotik_callback(callback: types.CallbackQuery):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён.", show_alert=True)
    
    mikrotik_id = callback.data.split(":", 1)[1]
    
    success, message = delete_mikrotik(mikrotik_id, callback.from_user.id)
    
    if success:
        await callback.message.edit_text(message)
    else:
        await callback.answer(message, show_alert=True)

# Обработчики состояний FSM для добавления микротика
@router.message(AddMikrotik.waiting_for_name)
async def process_mikrotik_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.reply("Введите хост API микротика (например, http://10.255.64.59:8780):")
    await state.set_state(AddMikrotik.waiting_for_host)

@router.message(AddMikrotik.waiting_for_host)
async def process_mikrotik_host(message: types.Message, state: FSMContext):
    await state.update_data(host=message.text)
    await message.reply("Введите имя пользователя для API:")
    await state.set_state(AddMikrotik.waiting_for_username)

@router.message(AddMikrotik.waiting_for_username)
async def process_mikrotik_username(message: types.Message, state: FSMContext):
    await state.update_data(username=message.text)
    await message.reply("Введите пароль для API:")
    await state.set_state(AddMikrotik.waiting_for_password)

@router.message(AddMikrotik.waiting_for_password)
async def process_mikrotik_password(message: types.Message, state: FSMContext):
    await state.update_data(password=message.text)
    await message.reply("Введите имя профиля OpenVPN:")
    await state.set_state(AddMikrotik.waiting_for_ovpn_profile)

@router.message(AddMikrotik.waiting_for_ovpn_profile)
async def process_mikrotik_ovpn_profile(message: types.Message, state: FSMContext):
    await state.update_data(ovpn_profile=message.text)
    await message.reply("Введите имя интерфейса WireGuard:")
    await state.set_state(AddMikrotik.waiting_for_wg_interface)

@router.message(AddMikrotik.waiting_for_wg_interface)
async def process_mikrotik_wg_interface(message: types.Message, state: FSMContext):
    await state.update_data(wg_interface=message.text)
    await message.reply("Введите endpoint WireGuard (например, my.example.domain:port wireguard или хх.хх.хх.хх:port wireguard):")
    await state.set_state(AddMikrotik.waiting_for_wg_endpoint)

@router.message(AddMikrotik.waiting_for_wg_endpoint)
async def process_mikrotik_wg_endpoint(message: types.Message, state: FSMContext):
    await state.update_data(wg_endpoint=message.text)
    await message.reply("Введите разрешенные IP-адреса WireGuard (через запятую, например: 172.22.14.0/24, 172.22.114.0/24 или если  весь траффик направлять в  туннель 0.0.0.0/0):")
    await state.set_state(AddMikrotik.waiting_for_wg_allowed_ips)

@router.message(AddMikrotik.waiting_for_wg_allowed_ips)
async def process_mikrotik_wg_allowed_ips(message: types.Message, state: FSMContext):
    # Обрабатываем разрешенные IP
    allowed_ips = [ip.strip() for ip in message.text.split(",")]
    
    # Получаем все данные из FSM
    data = await state.get_data()
    
    # Добавляем микротик
    success, result_message = add_mikrotik(
        name=data["name"],
        host=data["host"],
        username=data["username"],
        password=data["password"],
        openvpn_profile=data["ovpn_profile"],
        wg_interface_name=data["wg_interface"],
        wg_endpoint=data["wg_endpoint"],
        wg_allowed_ips=allowed_ips,
        admin_id=message.from_user.id
    )
    
    await message.reply(result_message)
    
    # Сбрасываем состояние
    await state.clear()

    # Возвращаем к главному меню с правильными кнопками
    from handlers.vpn import get_main_menu
    await message.answer(
        "Можете продолжить работу с ботом:",
        reply_markup=get_main_menu(message.from_user.id)
    )

# Обработчики для загрузки шаблона OpenVPN
@router.callback_query(F.data == "upload_template")
async def upload_template_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён.", show_alert=True)
    
    mikrotiks = get_mikrotik_list(callback.from_user.id)
    
    if not mikrotiks:
        return await callback.answer("Нет доступных микротиков.", show_alert=True)
    
    # Создаем inline-клавиатуру для выбора микротика
    buttons = []
    for mikrotik in mikrotiks:
        buttons.append([InlineKeyboardButton(text=mikrotik['name'], callback_data=f"select_mikrotik:{mikrotik['id']}")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await callback.message.reply("Выберите микротик для загрузки шаблона OpenVPN:", reply_markup=keyboard)
    await callback.answer()

@router.callback_query(F.data.startswith("select_mikrotik:"))
async def select_mikrotik_callback(callback: types.CallbackQuery, state: FSMContext):
    mikrotik_id = callback.data.split(":", 1)[1]
    await state.update_data(mikrotik_id=mikrotik_id)
    await callback.message.reply("Отправьте файл шаблона OpenVPN (.ovpn):")
    await state.set_state(UploadTemplate.waiting_for_template)
    await callback.answer()

@router.message(UploadTemplate.waiting_for_template)
async def process_template_file(message: types.Message, state: FSMContext, bot: Bot):
    # Проверяем, что отправлен файл
    if not message.document:
        await message.reply("Пожалуйста, отправьте файл шаблона .ovpn. Попробуйте еще раз.")
        return
    
    # Проверяем расширение файла
    if not message.document.file_name.endswith('.ovpn'):
        await message.reply("Файл должен иметь расширение .ovpn. Попробуйте еще раз.")
        return
    
    # Получаем ID микротика из состояния
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    # Загружаем файл (исправленный код)
    file_path = f"temp_{message.document.file_id}.ovpn"
    await bot.download(message.document, file_path)
    
    # Чтение содержимого файла
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # Загружаем шаблон
        success, result_message = upload_openvpn_template(mikrotik_id, template_content, message.from_user.id)
        
        await message.reply(result_message)
    except Exception as e:
        await message.reply(f"Ошибка при обработке файла: {e}")
    finally:
        # Удаляем временный файл
        import os
        if os.path.exists(file_path):
            os.unlink(file_path)
    
    # Сбрасываем состояние
    await state.clear()

# Обработчики для добавления администратора 2-го уровня
@router.callback_query(F.data == "add_admin")
async def add_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_level = check_admin_level(callback.from_user.id)
    
    if admin_level != 1:
        return await callback.answer("Доступ запрещён.", show_alert=True)
    
    await callback.message.reply("Введите ID пользователя Telegram для нового администратора 2-го уровня:")
    await state.set_state(AddAdmin.waiting_for_id)
    await callback.answer()

@router.message(AddAdmin.waiting_for_id)
async def process_admin_id(message: types.Message, state: FSMContext):
    try:
        admin_id = int(message.text)
        await state.update_data(admin_id=admin_id)
        await message.reply("Введите имя администратора:")
        await state.set_state(AddAdmin.waiting_for_name)
    except ValueError:
        await message.reply("ID должен быть числом. Попробуйте еще раз:")

@router.message(AddAdmin.waiting_for_name)
async def process_admin_name(message: types.Message, state: FSMContext):
    await state.update_data(admin_name=message.text)
    
    # Получаем список микротиков для выбора
    mikrotiks = get_mikrotik_list(message.from_user.id)
    
    if not mikrotiks:
        await message.reply("Нет доступных микротиков.")
        await state.clear()
        return
    
    # Создаем inline-клавиатуру для выбора микротиков
    buttons = []
    for mikrotik in mikrotiks:
        buttons.append([InlineKeyboardButton(
            text=mikrotik['name'], 
            callback_data=f"select_admin_mikrotik:{mikrotik['id']}"
        )])
    
    # Добавляем кнопку "Готово"
    buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="admin_mikrotiks_done")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    await message.reply(
        "Выберите микротики, к которым будет иметь доступ администратор. "
        "Нажмите на микротик, чтобы добавить/удалить его из списка. "
        "Когда закончите, нажмите 'Готово'.",
        reply_markup=keyboard
    )
    
    # Инициализируем список выбранных микротиков
    await state.update_data(selected_mikrotiks=[])
    await state.set_state(AddAdmin.waiting_for_mikrotiks)

@router.callback_query(F.data.startswith("select_admin_mikrotik:"))
async def select_admin_mikrotik_callback(callback: types.CallbackQuery, state: FSMContext):
    mikrotik_id = callback.data.split(":", 1)[1]
    
    # Получаем текущие выбранные микротики
    data = await state.get_data()
    selected_mikrotiks = data.get("selected_mikrotiks", [])
    
    # Добавляем или удаляем микротик из списка
    if mikrotik_id in selected_mikrotiks:
        selected_mikrotiks.remove(mikrotik_id)
    else:
        selected_mikrotiks.append(mikrotik_id)
    
    # Обновляем список выбранных микротиков
    await state.update_data(selected_mikrotiks=selected_mikrotiks)
    
    # Обновляем текст сообщения со списком выбранных микротиков
    mikrotiks = get_mikrotik_list(callback.from_user.id)
    selected_names = [m['name'] for m in mikrotiks if m['id'] in selected_mikrotiks]
    
    await callback.answer(f"{'Добавлен' if mikrotik_id in selected_mikrotiks else 'Удален'} микротик")
    
    if selected_names:
        await callback.message.edit_text(
            f"Выбранные микротики: {', '.join(selected_names)}\n\n"
            "Выберите микротики, к которым будет иметь доступ администратор. "
            "Нажмите на микротик, чтобы добавить/удалить его из списка. "
            "Когда закончите, нажмите 'Готово'.",
            reply_markup=callback.message.reply_markup
        )
    else:
        await callback.message.edit_text(
            "Не выбрано ни одного микротика.\n\n"
            "Выберите микротики, к которым будет иметь доступ администратор. "
            "Нажмите на микротик, чтобы добавить/удалить его из списка. "
            "Когда закончите, нажмите 'Готово'.",
            reply_markup=callback.message.reply_markup
        )

@router.callback_query(F.data == "admin_mikrotiks_done")
async def admin_mikrotiks_done_callback(callback: types.CallbackQuery, state: FSMContext):
    # Получаем данные из состояния
    data = await state.get_data()
    admin_id = data.get("admin_id")
    admin_name = data.get("admin_name")
    selected_mikrotiks = data.get("selected_mikrotiks", [])
    
    if not selected_mikrotiks:
        await callback.answer("Выберите хотя бы один микротик.", show_alert=True)
        return
    
    # Добавляем администратора
    success, result_message = add_level2_admin(
        admin_id, admin_name, selected_mikrotiks, callback.from_user.id
    )
    
    await callback.message.edit_text(result_message)
    
    # Сбрасываем состояние
    await state.clear()

# Обработчики для удаления администраторов
@router.callback_query(F.data.startswith("delete_admin_l2:"))
async def delete_admin_l2_callback(callback: types.CallbackQuery):
    admin_id = int(callback.data.split(":", 1)[1])
    
    success, result_message = delete_admin(admin_id, callback.from_user.id)
    
    if success:
        await callback.message.edit_text(result_message)
    else:
        await callback.answer(result_message, show_alert=True)