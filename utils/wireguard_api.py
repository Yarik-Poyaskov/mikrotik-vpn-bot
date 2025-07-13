import requests
import base64
import json
import re
import qrcode
import os
import tempfile
from io import BytesIO
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives import serialization

from utils.admin_utils import get_mikrotik_by_id

def get_wireguard_peers(mikrotik_id):
    """Получает список пиров WireGuard"""
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    
    try:
        response = requests.get(f"{BASE_URL}/interface/wireguard/peers", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        peers = response.json()
        
        # Сортируем пиры по имени
        peers.sort(key=lambda p: p.get('name', '').lower())
        
        return peers
    except requests.RequestException as e:
        return f"Ошибка получения пиров WireGuard: {e}"

def disable_wireguard_peer(peer_id, mikrotik_id):
    """Отключает пир WireGuard по ID"""
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    
    try:
        # Получаем текущий пир
        response = requests.get(f"{BASE_URL}/interface/wireguard/peers/{peer_id}", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        peer_data = response.json()
        
        # Устанавливаем disabled в true
        update_data = {"disabled": "true"}
        
        # Обновляем пир
        response = requests.patch(
            f"{BASE_URL}/interface/wireguard/peers/{peer_id}", 
            auth=AUTH, 
            verify=False, 
            json=update_data,
            timeout=5
        )
        response.raise_for_status()
        
        return f"✅ Пир {peer_data.get('name', 'Неизвестный')} успешно отключен."
    except requests.RequestException as e:
        return f"❌ Ошибка отключения пира: {e}"

def add_wireguard_peer(peer_name, mikrotik_id):
    """Добавляет новый пир WireGuard"""
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    WG_INTERFACE_NAME = mikrotik["wireguard"]["interface_name"]
    WG_ENDPOINT = mikrotik["wireguard"]["endpoint"]
    WG_ALLOWED_IPS = ", ".join(mikrotik["wireguard"]["allowed_ips"])
    
    try:
        # Проверяем, существует ли пир с таким именем
        peers = get_wireguard_peers(mikrotik_id)
        if isinstance(peers, str):
            return peers
        
        if any(p.get('name') == peer_name for p in peers):
            return f"⚠️ Пир с именем {peer_name} уже существует."
        
        # Генерируем ключи клиента
        private_key_obj = x25519.X25519PrivateKey.generate()
        private_key_bytes = private_key_obj.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_key_bytes = private_key_obj.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        private_key = base64.b64encode(private_key_bytes).decode('ascii')
        public_key = base64.b64encode(public_key_bytes).decode('ascii')
        
        # Получаем публичный ключ интерфейса сервера
        interface_response = requests.get(
            f"{BASE_URL}/interface/wireguard/{WG_INTERFACE_NAME}", 
            auth=AUTH, 
            verify=False,
            timeout=5
        )
        interface_response.raise_for_status()
        interface_data = interface_response.json()
        server_pubkey = interface_data.get("public-key")
        if not server_pubkey:
            return "❌ Публичный ключ интерфейса не найден"
        
        # Определяем подсеть и следующий свободный IP
        subnet_prefix = None
        max_ip_last_octet = 0
        
        for peer in peers:
            allowed_address = peer.get("allowed-address", "")
            match = re.match(r"^(\d+\.\d+\.\d+)\.(\d+)/32", allowed_address)
            if match:
                prefix = match.group(1)
                octet = int(match.group(2))
                if subnet_prefix is None:
                    subnet_prefix = prefix
                if prefix == subnet_prefix:
                    max_ip_last_octet = max(max_ip_last_octet, octet)
        
        if subnet_prefix is None:
            return "❌ Не удалось определить подсеть из существующих пиров"
        
        next_ip_last_octet = max_ip_last_octet + 1
        next_ip = f"{subnet_prefix}.{next_ip_last_octet}/32"
        ip_short = f"{subnet_prefix}.{next_ip_last_octet}"
        dns = f"{subnet_prefix}.1"
        
        # Формируем данные нового пира
        new_peer = {
            "interface": WG_INTERFACE_NAME,
            "name": peer_name,
            "public-key": public_key,
            "private-key": private_key,
            "allowed-address": next_ip,
            "disabled": "false",
            "comment": f"Added by VPN Bot"
        }
        
        # Отправляем запрос на создание пира
        response = requests.put(
            f"{BASE_URL}/interface/wireguard/peers", 
            auth=AUTH, 
            verify=False,
            json=new_peer,
            timeout=5
        )
        response.raise_for_status()
        
        # Генерируем .conf-файл с ключом сервера
        conf_text = f"""[Interface]
ListenPort = 51820
PrivateKey = {private_key}
Address = {next_ip}
DNS = {dns}

[Peer]
PublicKey = {server_pubkey}
AllowedIPs = {WG_ALLOWED_IPS}
Endpoint = {WG_ENDPOINT}
PersistentKeepalive = 20
"""
        
        # Создаем временный файл для конфигурации
        fd, temp_path = tempfile.mkstemp(suffix='.conf')
        with os.fdopen(fd, 'w') as temp_file:
            temp_file.write(conf_text)
        
        # Генерируем QR-код
        qr_img = qrcode.make(conf_text)
        qr_io = BytesIO()
        qr_img.save(qr_io, format='PNG')
        qr_io.seek(0)
        
        # Создаем временный файл для QR-кода
        qr_fd, qr_temp_path = tempfile.mkstemp(suffix='.png')
        with os.fdopen(qr_fd, 'wb') as qr_temp_file:
            qr_temp_file.write(qr_io.getvalue())
        
        return {
            "success": True,
            "name": peer_name,
            "conf_file": temp_path,
            "conf_filename": f"{peer_name}.conf",
            "qr_file": qr_temp_path,
            "qr_filename": f"{peer_name}.png",
            "message": f"✅ WireGuard пир {peer_name} успешно создан."
        }
        
    except requests.RequestException as e:
        error_msg = f"❌ Ошибка создания пира WireGuard: {e}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f"\nДетали: {e.response.text}"
        return error_msg
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def regenerate_wireguard_config(peer_id, mikrotik_id):
    """Регенерирует конфигурацию для существующего пира WireGuard"""
    # Получаем данные микротика
    mikrotik = get_mikrotik_by_id(mikrotik_id)
    if not mikrotik:
        return f"⚠️ Микротик не найден."
    
    BASE_URL = f"{mikrotik['host']}/rest"
    AUTH = (mikrotik["username"], mikrotik["password"])
    WG_INTERFACE_NAME = mikrotik["wireguard"]["interface_name"]
    WG_ENDPOINT = mikrotik["wireguard"]["endpoint"]
    WG_ALLOWED_IPS = ", ".join(mikrotik["wireguard"]["allowed_ips"])
    
    try:
        # Получаем текущий пир
        response = requests.get(f"{BASE_URL}/interface/wireguard/peers/{peer_id}", auth=AUTH, verify=False, timeout=5)
        response.raise_for_status()
        peer_data = response.json()
        
        # Получаем необходимые данные
        name = peer_data.get("name", "unknown")
        private_key = peer_data.get("private-key")
        allowed_address = peer_data.get("allowed-address", "")
        
        if not private_key:
            return f"❌ Приватный ключ для пира {name} не найден."
        
        # Получаем публичный ключ интерфейса сервера
        interface_response = requests.get(
            f"{BASE_URL}/interface/wireguard/{WG_INTERFACE_NAME}", 
            auth=AUTH, 
            verify=False,
            timeout=5
        )
        interface_response.raise_for_status()
        interface_data = interface_response.json()
        server_pubkey = interface_data.get("public-key")
        
        if not server_pubkey:
            return "❌ Публичный ключ интерфейса не найден"
        
        # Определяем DNS из подсети пира
        match = re.match(r"^(\d+\.\d+\.\d+)\.(\d+)/32", allowed_address)
        if not match:
            return f"❌ Не удалось определить подсеть из allowed-address: {allowed_address}"
        
        subnet_prefix = match.group(1)
        dns = f"{subnet_prefix}.1"
        
        # Генерируем .conf-файл с ключом сервера
        conf_text = f"""[Interface]
ListenPort = 51820
PrivateKey = {private_key}
Address = {allowed_address}
DNS = {dns}

[Peer]
PublicKey = {server_pubkey}
AllowedIPs = {WG_ALLOWED_IPS}
Endpoint = {WG_ENDPOINT}
PersistentKeepalive = 20
"""
        
        # Создаем временный файл для конфигурации
        fd, temp_path = tempfile.mkstemp(suffix='.conf')
        with os.fdopen(fd, 'w') as temp_file:
            temp_file.write(conf_text)
        
        # Генерируем QR-код
        qr_img = qrcode.make(conf_text)
        qr_io = BytesIO()
        qr_img.save(qr_io, format='PNG')
        qr_io.seek(0)
        
        # Создаем временный файл для QR-кода
        qr_fd, qr_temp_path = tempfile.mkstemp(suffix='.png')
        with os.fdopen(qr_fd, 'wb') as qr_temp_file:
            qr_temp_file.write(qr_io.getvalue())
        
        return {
            "success": True,
            "name": name,
            "conf_file": temp_path,
            "conf_filename": f"{name}.conf",
            "qr_file": qr_temp_path,
            "qr_filename": f"{name}.png",
            "message": f"✅ Конфигурация WireGuard для пира {name} успешно создана."
        }
        
    except requests.RequestException as e:
        error_msg = f"❌ Ошибка генерации конфигурации: {e}"
        if hasattr(e, 'response') and e.response is not None:
            error_msg += f"\nДетали: {e.response.text}"
        return error_msg
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"