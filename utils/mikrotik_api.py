import requests
import random
import string
from utils.admin_utils import get_mikrotik_by_id  

def get_openvpn_profile_credentials(name, mikrotik_id):
    """Получает данные профиля OpenVPN для скачивания"""
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    
    try:
        response = requests.get(f"{BASE_URL}/ppp/secret", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        secrets = response.json()
        
        # Ищем профиль с указанным именем
        for secret in secrets:
            if secret.get("name") == name and secret.get("service") == "ovpn":
                # Получаем пароль
                password = secret.get("password")
                if password:
                    return {
                        "success": True,
                        "name": name,
                        "password": password,
                        "message": f"✅ Получены данные профиля OpenVPN {name}."
                    }
        
        return f"⚠️ Профиль с именем {name} не найден."
    except requests.RequestException as e:
        return f"❌ Ошибка получения данных профиля: {e}"
    
def get_active_openvpn_profiles(mikrotik_id):
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    
    try:
        response = requests.get(f"{BASE_URL}/ppp/active", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        active_profiles = response.json()
        
        # Сортируем профили по алфавиту
        active_profiles.sort(key=lambda p: p.get('name', '').lower())
        
        return active_profiles
    except requests.RequestException as e:
        return f"Ошибка подключения к MikroTik: {e}"


def get_enabled_openvpn_profiles(mikrotik_id):
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    
    try:
        response = requests.get(f"{BASE_URL}/ppp/secret", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        all_profiles = response.json()
        
        # Фильтруем только НЕ отключенные OVPN профили
        enabled_profiles = [p for p in all_profiles if p.get("disabled") == "false" and p.get("service") == "ovpn"]
        
        # Сортируем профили по алфавиту
        enabled_profiles.sort(key=lambda p: p.get('name', '').lower())
        
        return enabled_profiles
    except requests.RequestException as e:
        return f"Ошибка подключения к MikroTik: {e}"


def deactivate_openvpn_profile(name, mikrotik_id):
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    
    try:
        response = requests.get(f"{BASE_URL}/ppp/active", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        active_profiles = response.json()
        
        for profile in active_profiles:
            if profile.get("name") == name:
                id_to_remove = profile.get(".id")
                if id_to_remove:
                    delete_response = requests.delete(
                        f"{BASE_URL}/ppp/active/{id_to_remove}", auth=AUTH, verify=False, timeout=5
                    )
                    delete_response.raise_for_status()
                    return f"✅ Профиль {name} успешно деактивирован."
        
        return f"⚠️ Профиль {name} не найден среди активных."
    except requests.RequestException as e:
        return f"❌ Ошибка деактивации профиля: {e}"


def disable_openvpn_secret(name, mikrotik_id):
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    
    try:
        response = requests.get(f"{BASE_URL}/ppp/secret", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        secrets = response.json()
        
        for secret in secrets:
            if secret.get("name") == name and secret.get("service") == "ovpn":
                id_to_disable = secret.get(".id")
                if id_to_disable:
                    patch_response = requests.patch(
                        f"{BASE_URL}/ppp/secret/{id_to_disable}",
                        auth=AUTH,
                        verify=False,
                        json={"disabled": "true"},
                        timeout=5
                    )
                    patch_response.raise_for_status()
                    return f"✅ Профиль {name} успешно отключен."
        
        return f"⚠️ Профиль {name} не найден."
    except requests.RequestException as e:
        return f"❌ Ошибка отключения профиля: {e}"


# Генерация пароля
def generate_password(length=15):
    """Генерирует пароль заданной длины с разными типами символов"""
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#%^&*"
    
    # Убедимся, что пароль содержит хотя бы один символ каждого типа
    password = [
        random.choice(lowercase),
        random.choice(uppercase),
        random.choice(digits),
        random.choice(special)
    ]
    
    # Добавляем остальные символы
    all_chars = lowercase + uppercase + digits + special
    password.extend(random.choice(all_chars) for _ in range(length - 4))
    
    # Перемешиваем символы
    random.shuffle(password)
    
    return ''.join(password)


# Проверка существования профиля
def check_profile_exists(name, mikrotik_id):
    """Проверяет, существует ли профиль с таким именем"""
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    
    try:
        response = requests.get(f"{BASE_URL}/ppp/secret", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        secrets = response.json()
        
        return any(s.get("name") == name for s in secrets)
    except requests.RequestException as e:
        return f"Ошибка проверки профиля: {e}"


def add_openvpn_profile(name, mikrotik_id):
    """Добавляет новый OpenVPN профиль"""
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    OVPN_PROFILE = mikrotik["openvpn"]["profile"]
    
    # Проверяем существование профиля
    exists_check = check_profile_exists(name, mikrotik_id)
    
    if isinstance(exists_check, str):
        return exists_check  # Вернуть ошибку, если она произошла
    
    if exists_check:
        return f"⚠️ Профиль с именем {name} уже существует."
    
    # Генерируем пароль
    password = generate_password(15)
    
    # Создаем новый профиль
    profile_data = {
        "name": name,
        "password": password,
        "service": "ovpn",
        "profile": OVPN_PROFILE
    }
    
    try:
        # Используем PUT запрос без /add, как в успешном тесте
        response = requests.put(
            f"{BASE_URL}/ppp/secret", 
            auth=AUTH,
            verify=False,
            json=profile_data,
            timeout=5
        )
        
        response.raise_for_status()
        
        # Возвращаем информацию о созданном профиле
        return {
            "success": True,
            "name": name,
            "password": password,
            "message": f"✅ Профиль {name} успешно создан."
        }
    except requests.RequestException as e:
        error_msg = f"❌ Ошибка создания профиля: {e}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f"\nДетали: {e.response.text}"
        return error_msg