import asyncio
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.utils.markdown import hbold, hcode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import os

from config import ALLOWED_USERS, ALLOWED_GROUPS
from utils.mikrotik_api import (
    get_active_openvpn_profiles,
    get_enabled_openvpn_profiles,
    deactivate_openvpn_profile,
    disable_openvpn_secret,
    add_openvpn_profile,
    get_openvpn_profile_credentials
)
from utils.wireguard_api import (
    get_wireguard_peers,
    disable_wireguard_peer,
    add_wireguard_peer,
    regenerate_wireguard_config
)
from utils.vpn_template import generate_ovpn_file
from utils.admin_utils import check_admin_level, get_mikrotik_by_id
from handlers.connection import get_current_mikrotik

# Добавляем константу для задержки перед удалением сообщений
AUTO_DELETE_DELAY = 30  # 30 секунд

router = Router()

# Определяем состояния для диалогов создания профилей
class ProfileCreation(StatesGroup):
    waiting_for_name = State()

class WireGuardProfileCreation(StatesGroup):
    waiting_for_name = State()

# Добавим состояния для пагинации
class PaginationData(StatesGroup):
    profiles_page = State()
    wireguard_page = State()

# Функция создания главного меню
def get_main_menu(user_id=None):
    """Создает главное меню с постоянными кнопками"""
    keyboard_layout = [
        [
            KeyboardButton(text="📋 OpenVPN Профили"),
            KeyboardButton(text="🔄 Активные OpenVPN")
        ],
        [
            KeyboardButton(text="🔷 WireGuard Профили"),
            KeyboardButton(text="➕ Добавить VPN")
        ],
        [
            KeyboardButton(text="🔄 Выбрать микротик")
        ]
    ]
    
    # Добавляем кнопки администратора для админов 1-го уровня
    if user_id and check_admin_level(user_id) == 1:
        keyboard_layout.append([
            KeyboardButton(text="⚙️ Админ-панель"),
            KeyboardButton(text="🔗 Подключение")
        ])
    
    keyboard = ReplyKeyboardMarkup(
        keyboard=keyboard_layout,
        resize_keyboard=True,
        one_time_keyboard=False,
        persistent=True
    )
    return keyboard

# Функция проверки наличия выбранного микротика
async def check_mikrotik_selected(message: types.Message, user_id: int):
    """Проверяет, выбран ли микротик, и если нет, предлагает выбрать"""
    mikrotik_id = get_current_mikrotik(user_id)
    
    if not mikrotik_id:
        await message.reply(
            "Сначала выберите микротик с которым хотите работать. "
            "Используйте команду /connect или кнопку 'Выбрать микротик'."
        )
        return False
    
    return True

def is_authorized(message: types.Message):
    # Проверяем уровень доступа пользователя
    admin_level = check_admin_level(message.from_user.id)
    if admin_level > 0:  # Если пользователь администратор 1-го или 2-го уровня
        return True
    
    # Проверяем старую логику для обратной совместимости
    if message.chat.type == "private":
        return message.from_user.id in ALLOWED_USERS
    elif message.chat.type in ["group", "supergroup"]:
        return message.chat.id in ALLOWED_GROUPS
    return False

def is_authorized_from_callback(callback: CallbackQuery):
    # Проверяем уровень доступа пользователя
    admin_level = check_admin_level(callback.from_user.id)
    if admin_level > 0:  # Если пользователь администратор 1-го или 2-го уровня
        return True
    
    # Проверяем старую логику для обратной совместимости
    chat = callback.message.chat
    if chat.type == "private":
        return callback.from_user.id in ALLOWED_USERS
    elif chat.type in ["group", "supergroup"]:
        return chat.id in ALLOWED_GROUPS
    return False

# Функция для удаления сообщения с задержкой
async def delete_message_after_delay(message: types.Message, delay: int):
    """Удаляет сообщение после указанной задержки в секундах"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        # Игнорируем ошибки при удалении, например, если сообщение уже удалено
        pass

# Обработчики для кнопок администратора 1-го уровня
@router.message(lambda message: message.text == "⚙️ Админ-панель")
async def handle_admin_panel_button(message: types.Message):
    if check_admin_level(message.from_user.id) != 1:
        return await message.reply("Доступ запрещён. Эта функция доступна только администраторам 1-го уровня.")
    
    # Импортируем функцию из admin_panel
    from handlers.admin_panel import get_admin_keyboard
    
    await message.reply(
        "Панель управления администратора 1-го уровня",
        reply_markup=get_admin_keyboard()
    )

@router.message(lambda message: message.text == "🏠 Главное меню")
async def handle_main_menu_button(message: types.Message):
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    await message.answer(
        "Главное меню VPN-бота:",
        reply_markup=get_main_menu(message.from_user.id)
    )

@router.message(lambda message: message.text == "🔗 Подключение")
async def handle_connection_button(message: types.Message):
    admin_level = check_admin_level(message.from_user.id)
    
    if admin_level == 0:
        return await message.reply("Доступ запрещён. Эта команда доступна только администраторам.")
    
    # Импортируем функцию из connection
    from handlers.connection import select_mikrotik_command
    await select_mikrotik_command(message)

# Команды для OpenVPN
@router.message(Command("status"))
async def openvpn_status_handler(message: types.Message):
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    await send_openvpn_status(message, mikrotik_id)

@router.message(Command("profile"))
async def openvpn_profile_handler(message: types.Message):
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    await send_openvpn_profiles(message, 1, mikrotik_id)

@router.message(Command("add_profile"))
async def add_profile_handler(message: types.Message, state: FSMContext):
    """Обработчик команды добавления профиля OpenVPN"""
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    await state.update_data(mikrotik_id=mikrotik_id)
    
    await message.reply("Введите имя нового OpenVPN профиля:")
    await state.set_state(ProfileCreation.waiting_for_name)

# Команды для WireGuard
@router.message(Command("wg_status"))
async def wireguard_status_handler(message: types.Message):
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    await send_wireguard_peers(message, 1, mikrotik_id)

@router.message(Command("add_wg"))
async def add_wireguard_handler(message: types.Message, state: FSMContext):
    """Обработчик команды добавления профиля WireGuard"""
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    await state.update_data(mikrotik_id=mikrotik_id)
    
    await message.reply("Введите имя нового WireGuard пира:")
    await state.set_state(WireGuardProfileCreation.waiting_for_name)

@router.message(Command("start"))
async def show_buttons(message: types.Message):
    if not is_authorized(message):
        return
    
    # Отправляем сообщение с главным меню
    await message.answer(
        "Главное меню VPN-бота. Сначала выберите микротик, используя кнопку 'Выбрать микротик'.",
        reply_markup=get_main_menu(message.from_user.id)  # Передаем user_id
    )

# Обрабатываем нажатие на кнопки главного меню
@router.message(lambda message: message.text == "📋 OpenVPN Профили")
async def handle_openvpn_profiles(message: types.Message):
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    await send_openvpn_profiles(message, 1, mikrotik_id)

@router.message(lambda message: message.text == "🔄 Активные OpenVPN")
async def handle_active_vpn(message: types.Message):
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    await send_openvpn_status(message, mikrotik_id)

@router.message(lambda message: message.text == "🔷 WireGuard Профили")
async def handle_wireguard_profiles(message: types.Message):
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    await send_wireguard_peers(message, 1, mikrotik_id)

@router.message(lambda message: message.text == "➕ Добавить VPN")
async def handle_add_vpn(message: types.Message):
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    
    # Показываем меню выбора типа VPN для добавления
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить OpenVPN", callback_data=f"add_profile:{mikrotik_id}")],
        [InlineKeyboardButton(text="Добавить WireGuard", callback_data=f"add_wireguard:{mikrotik_id}")]
    ])
    
    await message.answer(
        "Выберите тип VPN для добавления:",
        reply_markup=keyboard
    )

# Обработчики Callback-запросов для кнопок
@router.callback_query(F.data.startswith("ovpn_page:"))
async def openvpn_page_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    # Получаем номер страницы
    page = int(callback.data.split(":", 1)[1])
    
    # Проверяем, выбран ли микротик
    mikrotik_id = get_current_mikrotik(callback.from_user.id)
    if not mikrotik_id:
        await callback.message.reply(
            "Сначала выберите микротик. "
            "Используйте команду /connect или кнопку 'Выбрать микротик'."
        )
        return
    
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
    # Отправляем новую страницу
    await send_openvpn_profiles(callback.message, page, mikrotik_id)
    await callback.answer()

@router.callback_query(F.data.startswith("wg_page:"))
async def wireguard_page_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    # Получаем номер страницы
    page = int(callback.data.split(":", 1)[1])
    
    # Проверяем, выбран ли микротик
    mikrotik_id = get_current_mikrotik(callback.from_user.id)
    if not mikrotik_id:
        await callback.message.reply(
            "Сначала выберите микротик. "
            "Используйте команду /connect или кнопку 'Выбрать микротик'."
        )
        return
    
    # Удаляем старое сообщение
    try:
        await callback.message.delete()
    except:
        pass
    
    # Отправляем новую страницу
    await send_wireguard_peers(callback.message, page, mikrotik_id)
    await callback.answer()

@router.callback_query(F.data == "page_info")
async def page_info_callback(callback: CallbackQuery):
    """Обработчик для информационной кнопки с номером страницы"""
    await callback.answer("Используйте кнопки навигации для перехода между страницами", show_alert=True)

@router.callback_query(F.data.startswith("download_ovpn:"))
async def download_ovpn_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return await callback.answer("Неверный формат данных", show_alert=True)
    
    mikrotik_id = parts[1]
    name = parts[2]
    
    # Получаем данные профиля
    result = get_openvpn_profile_credentials(name, mikrotik_id)
    
    if isinstance(result, dict) and result.get("success"):
        # Получаем данные профиля
        name = result['name']
        password = result['password']
        
        try:
            # Генерируем .ovpn файл
            file_path, filename = generate_ovpn_file(name, password, mikrotik_id)
            
            # Создаем объект файла для отправки
            vpn_file = FSInputFile(file_path, filename=filename)
            
            # Отправляем файл
            await callback.message.answer_document(
                document=vpn_file,
                caption=f"✅ Профиль OpenVPN {hbold(name)} готов к использованию.",
                parse_mode="HTML"
            )
            
            # Удаляем временный файл после отправки
            os.unlink(file_path)
        except Exception as e:
            # Если произошла ошибка при генерации файла
            await callback.message.answer(
                f"⚠️ Не удалось создать файл профиля: {e}",
                parse_mode="HTML"
            )
    else:
        # Ошибка получения данных профиля
        await callback.message.answer(result)
    
    # Удаляем оригинальное сообщение с кнопками
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.answer()

@router.callback_query(F.data.startswith("download_wg:"))
async def download_wg_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return await callback.answer("Неверный формат данных", show_alert=True)
    
    mikrotik_id = parts[1]
    peer_id = parts[2]
    
    # Регенерируем конфигурацию с указанием микротика
    result = regenerate_wireguard_config(peer_id, mikrotik_id)
    
    if isinstance(result, dict) and result.get("success"):
        # Получаем данные
        name = result['name']
        conf_file = result['conf_file']
        conf_filename = result['conf_filename']
        qr_file = result['qr_file']
        qr_filename = result['qr_filename']
        
        try:
            # Создаем объекты файлов для отправки
            config_file = FSInputFile(conf_file, filename=conf_filename)
            qr_image = FSInputFile(qr_file, filename=qr_filename)
            
            # Отправляем файлы
            await callback.message.answer_document(
                document=config_file,
                caption=f"✅ Конфигурация WireGuard для пира {hbold(name)}.\n"
                        f"Ниже будет отправлен QR-код для сканирования.",
                parse_mode="HTML"
            )
            await callback.message.answer_photo(
                photo=qr_image,
                caption=f"QR-код для пира {hbold(name)}. Отсканируйте его в приложении WireGuard.",
                parse_mode="HTML"
            )
            
            # Удаляем временные файлы после отправки
            os.unlink(conf_file)
            os.unlink(qr_file)
        except Exception as e:
            # Если произошла ошибка при отправке файлов
            await callback.message.answer(
                f"⚠️ Не удалось отправить файлы: {e}",
                parse_mode="HTML"
            )
    else:
        # Ошибка регенерации конфигурации
        await callback.message.answer(result)
    
    # Удаляем оригинальное сообщение с кнопками
    try:
        await callback.message.delete()
    except:
        pass
    
    await callback.answer()

@router.callback_query(F.data == "show_status")
async def openvpn_status_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    mikrotik_id = get_current_mikrotik(callback.from_user.id)
    if not mikrotik_id:
        await callback.message.reply(
            "Сначала выберите микротик. "
            "Используйте команду /connect или кнопку 'Выбрать микротик'."
        )
        return
    
    await send_openvpn_status(callback.message, mikrotik_id)
    await callback.answer()

@router.callback_query(F.data == "show_profiles")
async def openvpn_profiles_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    mikrotik_id = get_current_mikrotik(callback.from_user.id)
    if not mikrotik_id:
        await callback.message.reply(
            "Сначала выберите микротик. "
            "Используйте команду /connect или кнопку 'Выбрать микротик'."
        )
        return
    
    await send_openvpn_profiles(callback.message, 1, mikrotik_id)
    await callback.answer()

@router.callback_query(F.data.startswith("add_profile:"))
async def add_profile_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки добавления профиля OpenVPN"""
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    mikrotik_id = callback.data.split(":", 1)[1]
    
    await state.update_data(mikrotik_id=mikrotik_id)
    await callback.message.reply("Введите имя нового OpenVPN профиля:")
    await state.set_state(ProfileCreation.waiting_for_name)
    await callback.answer()

@router.callback_query(F.data == "show_wireguard")
async def wireguard_peers_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    mikrotik_id = get_current_mikrotik(callback.from_user.id)
    if not mikrotik_id:
        await callback.message.reply(
            "Сначала выберите микротик. "
            "Используйте команду /connect или кнопку 'Выбрать микротик'."
        )
        return
    
    await send_wireguard_peers(callback.message, 1, mikrotik_id)
    await callback.answer()

@router.callback_query(F.data.startswith("add_wireguard:"))
async def add_wireguard_callback(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки добавления профиля WireGuard"""
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    mikrotik_id = callback.data.split(":", 1)[1]
    
    await state.update_data(mikrotik_id=mikrotik_id)
    await callback.message.reply("Введите имя нового WireGuard пира:")
    await state.set_state(WireGuardProfileCreation.waiting_for_name)
    await callback.answer()

@router.callback_query(F.data.startswith("deactivate:"))
async def deactivate_profile_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)

    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return await callback.answer("Неверный формат данных", show_alert=True)
    
    mikrotik_id = parts[1]
    name = parts[2]
    
    result = deactivate_openvpn_profile(name, mikrotik_id)
    
    # Результат теперь всегда строка с сообщением
    sent_msg = await callback.message.answer(result)
    
    # Удаляем оригинальное сообщение с кнопками
    try:
        await callback.message.delete()
    except:
        pass
        
    # Удаляем сообщение с результатом через минуту
    asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    
    await callback.answer()

@router.callback_query(F.data.startswith("disable:"))
async def disable_secret_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return await callback.answer("Неверный формат данных", show_alert=True)
    
    mikrotik_id = parts[1]
    name = parts[2]
    
    result = disable_openvpn_secret(name, mikrotik_id)
    
    sent_msg = await callback.message.answer(result)
    
    # Удаляем оригинальное сообщение с кнопками
    try:
        await callback.message.delete()
    except:
        pass
        
    # Удаляем сообщение с результатом через минуту
    asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    
    await callback.answer()

@router.callback_query(F.data.startswith("disable_wg:"))
async def disable_wireguard_callback(callback: CallbackQuery):
    if not is_authorized_from_callback(callback):
        return await callback.answer("Доступ запрещён", show_alert=True)
    
    parts = callback.data.split(":", 2)
    if len(parts) < 3:
        return await callback.answer("Неверный формат данных", show_alert=True)
    
    mikrotik_id = parts[1]
    peer_id = parts[2]
    
    result = disable_wireguard_peer(peer_id, mikrotik_id)
    
    sent_msg = await callback.message.answer(result)
    
    # Удаляем оригинальное сообщение с кнопками
    try:
        await callback.message.delete()
    except:
        pass
        
    # Удаляем сообщение с результатом через минуту
    asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    
    await callback.answer()

# Обработчики состояний FSM для создания профилей
@router.message(F.text.startswith("/find_ovpn"))
async def find_openvpn_profile(message: types.Message):
    """Поиск профиля OpenVPN по имени"""
    if not is_authorized(message):
        return await message.reply("Доступ запрещён.")
    
    # Проверяем, выбран ли микротик
    if not await check_mikrotik_selected(message, message.from_user.id):
        return
    
    mikrotik_id = get_current_mikrotik(message.from_user.id)
    
    # Извлекаем имя для поиска
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        return await message.reply("Использование: /find_ovpn <имя профиля>")
    
    search_name = parts[1].lower()
    
    # Получаем все профили
    profiles = get_enabled_openvpn_profiles(mikrotik_id)
    if isinstance(profiles, str):
        return await message.reply(profiles)
    
    # Ищем совпадения
    matching_profiles = [p for p in profiles if search_name in p.get('name', '').lower()]
    
    if not matching_profiles:
        return await message.reply(f"Профили, содержащие '{search_name}', не найдены.")
    
    # Создаем кнопки для найденных профилей
    buttons = []
    for p in matching_profiles[:10]:  # Ограничиваем 10 результатами
        name = p.get("name", "Неизвестно")
        row = [
            InlineKeyboardButton(text=f"📥 {name}", callback_data=f"download_ovpn:{mikrotik_id}:{name}"),
            InlineKeyboardButton(text=f"🗑️ {name}", callback_data=f"disable:{mikrotik_id}:{name}")
        ]
        buttons.append(row)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    sent_msg = await message.reply(
        f"Найдено профилей: {len(matching_profiles)}\n"
        f"Показаны первые {min(10, len(matching_profiles))}:",
        reply_markup=keyboard
    )
    
    asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))

@router.message(ProfileCreation.waiting_for_name)
async def process_profile_name(message: types.Message, state: FSMContext):
    """Обработчик имени профиля OpenVPN"""
    # Получаем имя профиля из сообщения
    profile_name = message.text.strip()
    
    # Проверяем корректность имени
    if not profile_name or len(profile_name) < 3:
        await message.reply("Имя профиля должно содержать минимум 3 символа. Попробуйте еще раз:")
        return
    
    # Предотвращаем использование специальных символов
    invalid_chars = "'\"\\/?*:;|<>, "
    if any(c in invalid_chars for c in profile_name):
        await message.reply(f"Имя профиля не должно содержать следующие символы: {invalid_chars}\nПопробуйте еще раз:")
        return
    
    # Получаем ID микротика из состояния
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    if not mikrotik_id:
        await message.reply("Ошибка: Не выбран микротик. Пожалуйста, начните заново.")
        await state.clear()
        return
    
    # Создаем профиль
    await message.reply(f"⏳ Создаю профиль OpenVPN {hbold(profile_name)}...")
    result = add_openvpn_profile(profile_name, mikrotik_id)
    
     # Сбрасываем состояние
    await state.clear()
    
    # Показываем сообщение с главным меню
    if isinstance(result, dict) and result.get("success"):
        # После отправки всех файлов
        await message.answer(
            "Операция завершена. Можете воспользоваться меню ниже.",
            reply_markup=get_main_menu(message.from_user.id)  # Передаем user_id
        )
    else:
        # В случае ошибки
        await message.answer(
            "Операция завершена. Можете воспользоваться меню ниже.",
            reply_markup=get_main_menu()
        )

    # Обрабатываем результат
    if isinstance(result, dict) and result.get("success"):
        # Получаем данные профиля
        name = result['name']
        password = result['password']
        creator_id = message.from_user.id
        creator_name = message.from_user.full_name
        
        # Получаем информацию о микротике для сообщения
        mikrotik_info = get_mikrotik_by_id(mikrotik_id)
        mikrotik_name = mikrotik_info.get("name", "Неизвестный микротик") if mikrotik_info else "Неизвестный микротик"
        
        try:
            # Генерируем .ovpn файл
            file_path, filename = generate_ovpn_file(name, password, mikrotik_id)
            
            # Создаем объект файла для отправки
            vpn_file = FSInputFile(file_path, filename=filename)
            
            # Отправляем файл создателю
            await message.reply_document(
                document=vpn_file,
                caption=f"✅ Профиль OpenVPN {hbold(name)} для {hbold(mikrotik_name)} успешно создан и готов к использованию.",
                parse_mode="HTML"
            )
            
            # Отправляем файл всем остальным администраторам
            bot = message.bot
            
            # Получаем список администраторов с доступом к этому микротику
            # admins_with_access = [] # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            from utils.admin_utils import load_admins
            admins_data = load_admins()
            
            # Добавляем админов 1-го уровня
            # admins_with_access.extend(admins_data["level_1"]) # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            admins_with_access = admins_data["level_1"]
            
            # Добавляем админов 2-го уровня с доступом к этому микротику
            # for admin in admins_data["level_2"]: # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            #    if mikrotik_id in admin.get("allowed_mikrotiks", []): # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            #        admins_with_access.append(admin["id"]) # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            
            # Делаем список уникальным
            # admins_with_access = list(set(admins_with_access)) # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            
            for admin_id in admins_with_access:
                # Пропускаем создателя, т.к. ему уже отправили
                if admin_id != creator_id:
                    try:
                        # Создаем новый объект файла для каждого админа
                        admin_vpn_file = FSInputFile(file_path, filename=filename)
                        await bot.send_document(
                            chat_id=admin_id,
                            document=admin_vpn_file,
                            caption=f"✅ Администратор {creator_name} создал новый профиль OpenVPN {hbold(name)} для {hbold(mikrotik_name)}.",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        # Логируем ошибку, но продолжаем работу
                        print(f"Не удалось отправить профиль администратору {admin_id}: {e}")
            
            # Удаляем временный файл после отправки
            os.unlink(file_path)
        except Exception as e:
            # Если произошла ошибка при генерации файла, выводим данные в текстовом виде
            await message.reply(
                f"{result['message']}\n\n"
                f"📝 Имя: {hbold(name)}\n"
                f"🔑 Пароль: {hcode(password)}\n\n"
                f"⚠️ Не удалось создать файл профиля: {e}",
                parse_mode="HTML"
            )
    else:
        # Ошибка создания профиля
        await message.reply(result)

@router.message(WireGuardProfileCreation.waiting_for_name)
async def process_wireguard_name(message: types.Message, state: FSMContext):
    """Обработчик имени пира WireGuard"""
    # Получаем имя пира из сообщения
    peer_name = message.text.strip()
    
    # Проверяем корректность имени
    if not peer_name or len(peer_name) < 3:
        await message.reply("Имя пира должно содержать минимум 3 символа. Попробуйте еще раз:")
        return
    
    # Предотвращаем использование специальных символов
    invalid_chars = "'\"\\/?*:;|<>, "
    if any(c in invalid_chars for c in peer_name):
        await message.reply(f"Имя пира не должно содержать следующие символы: {invalid_chars}\nПопробуйте еще раз:")
        return
    
    # Получаем ID микротика из состояния
    data = await state.get_data()
    mikrotik_id = data.get("mikrotik_id")
    
    if not mikrotik_id:
        await message.reply("Ошибка: Не выбран микротик. Пожалуйста, начните заново.")
        await state.clear()
        return
    
    # Создаем пир
    await message.reply(f"⏳ Создаю пир WireGuard {hbold(peer_name)}...")
    result = add_wireguard_peer(peer_name, mikrotik_id)
    
    # Получаем информацию о микротике для сообщения
    mikrotik_info = get_mikrotik_by_id(mikrotik_id)
    mikrotik_name = mikrotik_info.get("name", "Неизвестный микротик") if mikrotik_info else "Неизвестный микротик"
    
    # Обрабатываем результат
    if isinstance(result, dict) and result.get("success"):
        # Получаем данные пира
        name = result['name']
        conf_file = result['conf_file']
        conf_filename = result['conf_filename']
        qr_file = result['qr_file']
        qr_filename = result['qr_filename']
        creator_id = message.from_user.id
        creator_name = message.from_user.full_name
        
        try:
            # Создаем объекты файлов для отправки
            config_file = FSInputFile(conf_file, filename=conf_filename)
            qr_image = FSInputFile(qr_file, filename=qr_filename)
            
            # Отправляем файлы создателю
            await message.reply_document(
                document=config_file,
                caption=f"✅ Пир WireGuard {hbold(name)} для {hbold(mikrotik_name)} успешно создан.\n"
                        f"Конфигурационный файл и QR-код для сканирования:",
                parse_mode="HTML"
            )
            await message.reply_photo(
                photo=qr_image,
                caption=f"QR-код для пира {hbold(name)}. Отсканируйте его в приложении WireGuard.",
                parse_mode="HTML"
            )
            
            # Отправляем файлы всем остальным администраторам с доступом к этому микротику
            bot = message.bot
            
            # Получаем список администраторов с доступом к этому микротику
            # admins_with_access = [] # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            from utils.admin_utils import load_admins
            admins_data = load_admins()
            
            # Добавляем админов 1-го уровня
            # admins_with_access.extend(admins_data["level_1"]) # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            # Только админы 1-го уровня получают уведомления
            admins_with_access = admins_data["level_1"]
            
            # Добавляем админов 2-го уровня с доступом к этому микротику
            # for admin in admins_data["level_2"]: # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            #    if mikrotik_id in admin.get("allowed_mikrotiks", []): # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            #        admins_with_access.append(admin["id"]) # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            
            # Делаем список уникальным
            # admins_with_access = list(set(admins_with_access)) # Раскоментировать  если нужно  чтобы  получали  админы  2го  уровня
            
            for admin_id in admins_with_access:
                # Пропускаем создателя, т.к. ему уже отправили
                if admin_id != creator_id:
                    try:
                        # Создаем новые объекты файлов для каждого админа
                        admin_config_file = FSInputFile(conf_file, filename=conf_filename)
                        admin_qr_image = FSInputFile(qr_file, filename=qr_filename)
                        
                        await bot.send_document(
                            chat_id=admin_id,
                            document=admin_config_file,
                            caption=f"✅ Администратор {creator_name} создал новый пир WireGuard {hbold(name)} для {hbold(mikrotik_name)}.\n"
                                    f"Конфигурационный файл и QR-код для сканирования:",
                            parse_mode="HTML"
                        )
                        await bot.send_photo(
                            chat_id=admin_id,
                            photo=admin_qr_image,
                            caption=f"QR-код для пира {hbold(name)}. Отсканируйте его в приложении WireGuard.",
                            parse_mode="HTML"
                        )
                    except Exception as e:
                        # Логируем ошибку, но продолжаем работу
                        print(f"Не удалось отправить файлы WireGuard администратору {admin_id}: {e}")
            
            # Удаляем временные файлы после отправки
            os.unlink(conf_file)
            os.unlink(qr_file)
        except Exception as e:
            # Если произошла ошибка при генерации файлов
            await message.reply(
                f"{result['message']}\n\n"
                f"⚠️ Не удалось создать файлы: {e}",
                parse_mode="HTML"
            )
    else:
        # Ошибка создания пира
        await message.reply(result)
    
    # Сбрасываем состояние
    await state.clear()
    
    # Показываем сообщение с главным меню
    await message.answer(
        "Операция завершена. Можете воспользоваться меню ниже.",
        reply_markup=get_main_menu(message.from_user.id)  # Передаем user_id
    )

# Функции отправки данных
async def send_openvpn_status(message: types.Message, mikrotik_id: str):
    profiles = get_active_openvpn_profiles(mikrotik_id)
    
    # Получаем информацию о микротике для сообщения
    mikrotik_info = get_mikrotik_by_id(mikrotik_id)
    mikrotik_name = mikrotik_info.get("name", "Неизвестный микротик") if mikrotik_info else "Неизвестный микротик"
    
    if isinstance(profiles, str):
        # Сообщение с ошибкой (будем удалять)
        sent_msg = await message.answer(profiles)
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    elif not profiles:
        # Сообщение об отсутствии профилей (будем удалять)
        sent_msg = await message.answer(f"Нет активных OVPN профилей на {hbold(mikrotik_name)}.", parse_mode="HTML")
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    else:
        # Сортируем профили в алфавитном порядке по имени
        profiles = sorted(profiles, key=lambda p: p.get('name', '').lower())
        
        # Создаем сетку кнопок (по 2 кнопки в ряд)
        buttons = []
        row = []
        for i, p in enumerate(profiles):
            name = p.get("name", "Неизвестно")
            row.append(InlineKeyboardButton(text=f"🔴 {name}", callback_data=f"deactivate:{mikrotik_id}:{name}"))
            
            # Добавляем по 2 кнопки в ряд
            if len(row) == 2 or i == len(profiles) - 1:
                buttons.append(row)
                row = []
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        # Отправляем сообщение с inline-клавиатурой, которое будет удалено
        sent_msg = await message.answer(
            f"Активные профили OpenVPN на {hbold(mikrotik_name)}:", 
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        # Планируем удаление сообщения
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))

async def send_openvpn_profiles(message: types.Message, page: int = 1, mikrotik_id: str = None):
    # Если mikrotik_id не передан, попробуем его получить
    if not mikrotik_id:
        mikrotik_id = get_current_mikrotik(message.from_user.id)
        if not mikrotik_id:
            await message.answer(
                "Сначала выберите микротик. "
                "Используйте команду /connect или кнопку 'Выбрать микротик'."
            )
            return
    
    # Получаем информацию о микротике для сообщения
    mikrotik_info = get_mikrotik_by_id(mikrotik_id)
    mikrotik_name = mikrotik_info.get("name", "Неизвестный микротик") if mikrotik_info else "Неизвестный микротик"
    
    profiles = get_enabled_openvpn_profiles(mikrotik_id)
    
    if isinstance(profiles, str):
        sent_msg = await message.answer(profiles)
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    elif not profiles:
        sent_msg = await message.answer(f"Нет доступных OpenVPN профилей на {hbold(mikrotik_name)}.", parse_mode="HTML")
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    else:
        # Сортируем профили
        profiles = sorted(profiles, key=lambda p: p.get('name', '').lower())
        
        # Параметры пагинации
        items_per_page = 10  # 10 профилей на страницу (20 кнопок)
        total_pages = (len(profiles) + items_per_page - 1) // items_per_page
        
        # Проверяем корректность страницы
        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages
        
        # Вычисляем срез для текущей страницы
        start_idx = (page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(profiles))
        current_profiles = profiles[start_idx:end_idx]
        
        # Создаем кнопки для текущей страницы
        buttons = []
        for p in current_profiles:
            name = p.get("name", "Неизвестно")
            row = [
                InlineKeyboardButton(text=f"📥 {name}", callback_data=f"download_ovpn:{mikrotik_id}:{name}"),
                InlineKeyboardButton(text=f"🗑️ {name}", callback_data=f"disable:{mikrotik_id}:{name}")
            ]
            buttons.append(row)
        
        # Добавляем кнопки навигации
        nav_buttons = []
        
        # Кнопка "Предыдущая"
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"ovpn_page:{page-1}"))
        
        # Информация о текущей странице
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"ovpn_page:{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        sent_msg = await message.answer(
            f"Профили OpenVPN на {hbold(mikrotik_name)} (страница {page}/{total_pages}):\n"
            f"📥 - Скачать профиль\n"
            f"🗑️ - Удалить профиль\n"
            f"Всего профилей: {len(profiles)}", 
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY * 2))  # Увеличиваем время для навигации

async def send_wireguard_peers(message: types.Message, page: int = 1, mikrotik_id: str = None):
    # Если mikrotik_id не передан, попробуем его получить
    if not mikrotik_id:
        mikrotik_id = get_current_mikrotik(message.from_user.id)
        if not mikrotik_id:
            await message.answer(
                "Сначала выберите микротик. "
                "Используйте команду /connect или кнопку 'Выбрать микротик'."
            )
            return
    
    # Получаем информацию о микротике для сообщения
    mikrotik_info = get_mikrotik_by_id(mikrotik_id)
    mikrotik_name = mikrotik_info.get("name", "Неизвестный микротик") if mikrotik_info else "Неизвестный микротик"
    
    peers = get_wireguard_peers(mikrotik_id)
    
    if isinstance(peers, str):
        sent_msg = await message.answer(peers)
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    elif not peers:
        sent_msg = await message.answer(f"Нет доступных пиров WireGuard на {hbold(mikrotik_name)}.", parse_mode="HTML")
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
    else:
        # Фильтруем только активные пиры (не отключенные)
        active_peers = [p for p in peers if p.get("disabled") == "false"]
        
        if not active_peers:
            sent_msg = await message.answer(f"Нет активных пиров WireGuard на {hbold(mikrotik_name)}.", parse_mode="HTML")
            asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY))
            return
        
        # Сортируем пиры
        active_peers = sorted(active_peers, key=lambda p: p.get('name', '').lower())
        
        # Параметры пагинации
        items_per_page = 10  # 10 пиров на страницу
        total_pages = (len(active_peers) + items_per_page - 1) // items_per_page
        
        # Проверяем корректность страницы
        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages
        
        # Вычисляем срез для текущей страницы
        start_idx = (page - 1) * items_per_page
        end_idx = min(start_idx + items_per_page, len(active_peers))
        current_peers = active_peers[start_idx:end_idx]
        
        # Создаем кнопки для текущей страницы
        buttons = []
        for p in current_peers:
            name = p.get("name", "Неизвестно")
            peer_id = p.get(".id", "")
            if peer_id:
                row = [
                    InlineKeyboardButton(text=f"📥 {name}", callback_data=f"download_wg:{mikrotik_id}:{peer_id}"),
                    InlineKeyboardButton(text=f"🗑️ {name}", callback_data=f"disable_wg:{mikrotik_id}:{peer_id}")
                ]
                buttons.append(row)
        
        # Добавляем кнопки навигации
        nav_buttons = []
        
        # Кнопка "Предыдущая"
        if page > 1:
            nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"wg_page:{page-1}"))
        
        # Информация о текущей странице
        nav_buttons.append(InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="page_info"))
        
        # Кнопка "Следующая"
        if page < total_pages:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"wg_page:{page+1}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
        
        sent_msg = await message.answer(
            f"Пиры WireGuard на {hbold(mikrotik_name)} (страница {page}/{total_pages}):\n"
            f"📥 - Скачать конфигурацию\n"
            f"🗑️ - Удалить пир\n"
            f"Всего активных пиров: {len(active_peers)}", 
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        asyncio.create_task(delete_message_after_delay(sent_msg, AUTO_DELETE_DELAY * 2))