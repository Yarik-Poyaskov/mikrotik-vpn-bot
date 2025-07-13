import logging
from datetime import datetime

# Настройка логирования
def setup_logger():
    logger = logging.getLogger('vpn_bot')
    logger.setLevel(logging.INFO)
    
    # Создаем обработчик для записи в файл
    file_handler = logging.FileHandler(f'logs/vpn_bot_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler.setLevel(logging.INFO)
    
    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    
    # Создаем форматтер
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчики к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger