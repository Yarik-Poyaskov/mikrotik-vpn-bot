import os
import tempfile

def generate_ovpn_file(username, password, mikrotik_id):
    """
    Генерирует .ovpn файл на основе шаблона c указанными учетными данными
    
    Args:
        username: Имя пользователя VPN
        password: Пароль пользователя VPN
        mikrotik_id: ID микротика
        
    Returns:
        Путь к сгенерированному файлу
    """
    # Определяем путь к шаблону
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'templates', 
        'mikrotik_templates', 
        mikrotik_id, 
        'openvpn_template.ovpn'
    )
    
    # Если шаблон не существует, используем стандартный шаблон
    if not os.path.exists(template_path):
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'templates', 
            'openvpn_template.ovpn'
        )
    
    # Создаем имя файла
    filename = f"{username}.ovpn"
    
    # Создаем временный файл
    fd, temp_path = tempfile.mkstemp(suffix='.ovpn')
    
    try:
        # Читаем шаблон
        with open(template_path, 'r', encoding='utf-8') as template_file:
            template_content = template_file.read()
        
        # Заменяем плейсхолдеры на реальные данные
        file_content = template_content.replace('{username}', username).replace('{password}', password)
        
        # Записываем содержимое в файл
        with os.fdopen(fd, 'w', encoding='utf-8') as temp_file:
            temp_file.write(file_content)
        
        return temp_path, filename
    except Exception as e:
        # В случае ошибки закрываем дескриптор и удаляем файл
        os.close(fd)
        os.unlink(temp_path)
        raise e