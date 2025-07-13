import json
import os
import uuid
from typing import List, Dict, Any, Union, Tuple

# Пути к файлам данных
MIKROTIKS_FILE = 'data/mikrotiks.json'
ADMINS_FILE = 'data/admins.json'

# Создаем директорию и файлы, если их нет
os.makedirs('data', exist_ok=True)
if not os.path.exists(MIKROTIKS_FILE):
    with open(MIKROTIKS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"mikrotiks": []}, f, indent=2)

if not os.path.exists(ADMINS_FILE):
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump({"level_1": [], "level_2": []}, f, indent=2)

def load_mikrotiks() -> Dict:
    """Загружает список микротиков из файла"""
    with open(MIKROTIKS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_mikrotiks(data: Dict) -> None:
    """Сохраняет список микротиков в файл"""
    with open(MIKROTIKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def load_admins() -> Dict:
    """Загружает список администраторов из файла"""
    with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_admins(data: Dict) -> None:
    """Сохраняет список администраторов в файл"""
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def check_admin_level(user_id: int) -> int:
    """
    Проверяет уровень администратора.
    Возвращает: 1 - для админа 1-го уровня, 2 - для админа 2-го уровня, 0 - не админ
    """
    admins = load_admins()
    
    if user_id in admins["level_1"]:
        return 1
    
    for admin in admins["level_2"]:
        if admin["id"] == user_id:
            return 2
    
    return 0

def get_allowed_mikrotiks(user_id: int) -> List[str]:
    """Возвращает список ID микротиков, доступных администратору"""
    admins = load_admins()
    mikrotiks_data = load_mikrotiks()
    mikrotik_ids = [m["id"] for m in mikrotiks_data["mikrotiks"]]
    
    # Админы 1-го уровня имеют доступ ко всем микротикам
    if user_id in admins["level_1"]:
        return mikrotik_ids
    
    # Админы 2-го уровня имеют доступ только к разрешенным микротикам
    for admin in admins["level_2"]:
        if admin["id"] == user_id:
            return admin["allowed_mikrotiks"]
    
    return []

def add_mikrotik(
    name: str, 
    host: str, 
    username: str, 
    password: str, 
    openvpn_profile: str,
    wg_interface_name: str,
    wg_endpoint: str,
    wg_allowed_ips: List[str],
    admin_id: int
) -> Tuple[bool, str]:
    """
    Добавляет новый микротик
    
    Returns:
        (success, message): Кортеж с результатом операции
    """
    # Проверяем права администратора
    if check_admin_level(admin_id) != 1:
        return False, "Доступ запрещён. Требуется уровень администратора 1."
    
    mikrotiks_data = load_mikrotiks()
    
    # Генерируем уникальный ID для микротика
    mikrotik_id = f"mikrotik_{str(uuid.uuid4())[:8]}"
    
    # Создаем директорию для шаблонов этого микротика
    template_dir = os.path.join('templates', 'mikrotik_templates', mikrotik_id)
    os.makedirs(template_dir, exist_ok=True)
    
    # Создаем структуру данных для нового микротика
    new_mikrotik = {
        "id": mikrotik_id,
        "name": name,
        "host": host,
        "username": username,
        "password": password,
        "openvpn": {
            "profile": openvpn_profile
        },
        "wireguard": {
            "interface_name": wg_interface_name,
            "endpoint": wg_endpoint,
            "allowed_ips": wg_allowed_ips
        }
    }
    
    # Добавляем микротик в список
    mikrotiks_data["mikrotiks"].append(new_mikrotik)
    save_mikrotiks(mikrotiks_data)
    
    return True, f"Микротик {name} успешно добавлен с ID {mikrotik_id}"

def upload_openvpn_template(mikrotik_id: str, template_content: str, admin_id: int) -> Tuple[bool, str]:
    """
    Загружает шаблон OpenVPN для микротика
    
    Returns:
        (success, message): Кортеж с результатом операции
    """
    # Проверяем права администратора
    if check_admin_level(admin_id) != 1:
        return False, "Доступ запрещён. Требуется уровень администратора 1."
    
    mikrotiks_data = load_mikrotiks()
    
    # Проверяем существование микротика
    mikrotik_exists = False
    mikrotik_name = ""
    
    for mikrotik in mikrotiks_data["mikrotiks"]:
        if mikrotik["id"] == mikrotik_id:
            mikrotik_exists = True
            mikrotik_name = mikrotik.get("name", "")
            break
    
    if not mikrotik_exists:
        return False, f"Микротик с ID {mikrotik_id} не найден."
    
    # Сохраняем шаблон
    template_dir = os.path.join('templates', 'mikrotik_templates', mikrotik_id)
    os.makedirs(template_dir, exist_ok=True)
    
    template_path = os.path.join(template_dir, 'openvpn_template.ovpn')
    
    try:
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        return True, f"✅ Шаблон OpenVPN для микротика {mikrotik_name} (ID: {mikrotik_id}) успешно загружен."
    except Exception as e:
        return False, f"❌ Ошибка при сохранении шаблона: {e}"

def add_level2_admin(
    new_admin_id: int, 
    name: str, 
    allowed_mikrotiks: List[str], 
    creator_id: int
) -> Tuple[bool, str]:
    """
    Добавляет администратора 2-го уровня
    
    Returns:
        (success, message): Кортеж с результатом операции
    """
    # Проверяем права создателя
    if check_admin_level(creator_id) != 1:
        return False, "Доступ запрещён. Требуется уровень администратора 1."
    
    admins_data = load_admins()
    
    # Проверяем, что админ не существует
    if new_admin_id in admins_data["level_1"]:
        return False, f"Пользователь {new_admin_id} уже является администратором 1-го уровня."
    
    for admin in admins_data["level_2"]:
        if admin["id"] == new_admin_id:
            return False, f"Пользователь {new_admin_id} уже является администратором 2-го уровня."
    
    # Проверяем существование микротиков
    mikrotiks_data = load_mikrotiks()
    existing_mikrotik_ids = [m["id"] for m in mikrotiks_data["mikrotiks"]]
    
    for mikrotik_id in allowed_mikrotiks:
        if mikrotik_id not in existing_mikrotik_ids:
            return False, f"Микротик с ID {mikrotik_id} не существует."
    
    # Добавляем нового администратора
    new_admin = {
        "id": new_admin_id,
        "name": name,
        "allowed_mikrotiks": allowed_mikrotiks
    }
    
    admins_data["level_2"].append(new_admin)
    save_admins(admins_data)
    
    return True, f"Администратор {name} (ID: {new_admin_id}) успешно добавлен."

def get_mikrotik_by_id(mikrotik_id: str) -> Union[Dict, None]:
    """Возвращает данные микротика по ID"""
    mikrotiks_data = load_mikrotiks()
    
    for mikrotik in mikrotiks_data["mikrotiks"]:
        if mikrotik["id"] == mikrotik_id:
            return mikrotik
    
    return None

def get_mikrotik_list(user_id: int) -> List[Dict]:
    """Возвращает список микротиков, доступных пользователю"""
    allowed_mikrotik_ids = get_allowed_mikrotiks(user_id)
    mikrotiks_data = load_mikrotiks()
    
    return [
        {"id": m["id"], "name": m["name"]} 
        for m in mikrotiks_data["mikrotiks"] 
        if m["id"] in allowed_mikrotik_ids
    ]

def delete_mikrotik(mikrotik_id: str, admin_id: int) -> Tuple[bool, str]:
    """Удаляет микротик"""
    # Проверяем права администратора
    if check_admin_level(admin_id) != 1:
        return False, "Доступ запрещён. Требуется уровень администратора 1."
    
    mikrotiks_data = load_mikrotiks()
    
    # Ищем микротик для удаления
    for i, mikrotik in enumerate(mikrotiks_data["mikrotiks"]):
        if mikrotik["id"] == mikrotik_id:
            # Удаляем микротик из списка
            del mikrotiks_data["mikrotiks"][i]
            save_mikrotiks(mikrotiks_data)
            
            # Удаляем шаблоны
            template_dir = os.path.join('templates', 'mikrotik_templates', mikrotik_id)
            if os.path.exists(template_dir):
                import shutil
                shutil.rmtree(template_dir)
            
            # Удаляем разрешения для админов 2-го уровня
            admins_data = load_admins()
            for admin in admins_data["level_2"]:
                if mikrotik_id in admin["allowed_mikrotiks"]:
                    admin["allowed_mikrotiks"].remove(mikrotik_id)
            save_admins(admins_data)
            
            return True, f"Микротик {mikrotik_id} успешно удален."
    
    return False, f"Микротик с ID {mikrotik_id} не найден."

def delete_admin(admin_id: int, creator_id: int) -> Tuple[bool, str]:
    """Удаляет администратора 2-го уровня"""
    # Проверяем права создателя
    if check_admin_level(creator_id) != 1:
        return False, "Доступ запрещён. Требуется уровень администратора 1."
    
    admins_data = load_admins()
    
    # Ищем админа для удаления
    for i, admin in enumerate(admins_data["level_2"]):
        if admin["id"] == admin_id:
            del admins_data["level_2"][i]
            save_admins(admins_data)
            return True, f"Администратор {admin_id} успешно удален."
    
    return False, f"Администратор с ID {admin_id} не найден."

def edit_mikrotik_field(mikrotik_id: str, field: str, value, admin_id: int) -> Tuple[bool, str]:
    """
    Редактирует поле микротика
    
    Args:
        mikrotik_id: ID микротика
        field: Название поля для редактирования
        value: Новое значение
        admin_id: ID администратора
        
    Returns:
        (success, message): Кортеж с результатом операции
    """
    # Проверяем права администратора
    if check_admin_level(admin_id) != 1:
        return False, "Доступ запрещён. Требуется уровень администратора 1."
    
    mikrotiks_data = load_mikrotiks()
    
    # Ищем микротик для редактирования
    mikrotik_found = False
    mikrotik_idx = -1
    for idx, mikrotik in enumerate(mikrotiks_data["mikrotiks"]):
        if mikrotik["id"] == mikrotik_id:
            mikrotik_found = True
            mikrotik_idx = idx
            break
    
    if not mikrotik_found:
        return False, f"Микротик с ID {mikrotik_id} не найден."
    
    # Редактируем соответствующее поле
    if field in ["name", "host", "username", "password"]:
        mikrotiks_data["mikrotiks"][mikrotik_idx][field] = value
    elif field == "ovpn_profile":
        mikrotiks_data["mikrotiks"][mikrotik_idx]["openvpn"]["profile"] = value
    elif field == "wg_interface":
        mikrotiks_data["mikrotiks"][mikrotik_idx]["wireguard"]["interface_name"] = value
    elif field == "wg_endpoint":
        mikrotiks_data["mikrotiks"][mikrotik_idx]["wireguard"]["endpoint"] = value
    elif field == "wg_allowed_ips":
        mikrotiks_data["mikrotiks"][mikrotik_idx]["wireguard"]["allowed_ips"] = value
    else:
        return False, f"Неизвестное поле {field}."
    
    # Сохраняем изменения
    save_mikrotiks(mikrotiks_data)
    
    return True, f"✅ Поле {field} успешно обновлено."

def update_admin_name(admin_id: int, new_name: str, editor_id: int) -> Tuple[bool, str]:
    """Обновляет имя администратора 2-го уровня"""
    if check_admin_level(editor_id) != 1:
        return False, "Доступ запрещён."
    
    admins_data = load_admins()
    
    for admin in admins_data["level_2"]:
        if admin["id"] == admin_id:
            admin["name"] = new_name
            save_admins(admins_data)
            return True, f"✅ Имя администратора изменено на '{new_name}'"
    
    return False, "Администратор не найден."

def update_admin_mikrotiks(admin_id: int, mikrotik_ids: List[str], editor_id: int) -> Tuple[bool, str]:
    """Обновляет список доступных микротиков для администратора 2-го уровня"""
    if check_admin_level(editor_id) != 1:
        return False, "Доступ запрещён."
    
    admins_data = load_admins()
    
    for admin in admins_data["level_2"]:
        if admin["id"] == admin_id:
            admin["allowed_mikrotiks"] = mikrotik_ids
            save_admins(admins_data)
            return True, f"✅ Доступ к микротикам обновлен для администратора {admin.get('name', admin_id)}"
    
    return False, "Администратор не найден."

def promote_admin_to_level1(admin_id: int, editor_id: int) -> Tuple[bool, str]:
    """Повышает администратора 2-го уровня до 1-го уровня"""
    if check_admin_level(editor_id) != 1:
        return False, "Доступ запрещён."
    
    admins_data = load_admins()
    
    # Находим админа 2-го уровня
    admin_to_promote = None
    for i, admin in enumerate(admins_data["level_2"]):
        if admin["id"] == admin_id:
            admin_to_promote = admin
            del admins_data["level_2"][i]
            break
    
    if not admin_to_promote:
        return False, "Администратор не найден."
    
    # Добавляем в админы 1-го уровня
    if admin_id not in admins_data["level_1"]:
        admins_data["level_1"].append(admin_id)
    
    save_admins(admins_data)
    return True, f"✅ Администратор {admin_to_promote.get('name', admin_id)} повышен до 1-го уровня"

def demote_admin_to_level2(admin_id: int, name: str, editor_id: int) -> Tuple[bool, str]:
    """Понижает администратора 1-го уровня до 2-го уровня"""
    if check_admin_level(editor_id) != 1:
        return False, "Доступ запрещён."
    
    admins_data = load_admins()
    
    if admin_id not in admins_data["level_1"]:
        return False, "Администратор не найден среди админов 1-го уровня."
    
    # Удаляем из админов 1-го уровня
    admins_data["level_1"].remove(admin_id)
    
    # Добавляем в админы 2-го уровня с пустым списком микротиков
    new_admin = {
        "id": admin_id,
        "name": name,
        "allowed_mikrotiks": []
    }
    
    admins_data["level_2"].append(new_admin)
    
    save_admins(admins_data)
    return True, f"✅ Администратор {name} понижен до 2-го уровня"