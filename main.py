import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from handlers import vpn, admin_panel, connection
from utils.logging import setup_logger

# Отключаем предупреждения о небезопасных HTTPS запросах
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Создаем необходимые папки, если их нет
os.makedirs('logs', exist_ok=True)
os.makedirs('templates', exist_ok=True)
os.makedirs('data', exist_ok=True)
os.makedirs('templates/mikrotik_templates', exist_ok=True)

# Настраиваем логирование
logger = setup_logger()

async def main():
    logger.info("Бот запускается...")
    
    # Создаем хранилище для FSM
    storage = MemoryStorage()
    
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    # Подключаем обработчики
    dp.include_router(connection.router)  # Обработчики выбора микротика
    dp.include_router(admin_panel.router)  # Обработчики админ-панели
    dp.include_router(vpn.router)  # Обработчики VPN

    # Загружаем список администраторов 1-го уровня из конфигурационного файла
    from utils.admin_utils import load_admins, save_admins
    from config import ALLOWED_USERS
    
    # Инициализируем файл с администраторами, если он не существует
    try:
        admins = load_admins()
        # Обновляем список администраторов 1-го уровня из конфигурационного файла
        admins["level_1"] = ALLOWED_USERS
        save_admins(admins)
    except Exception as e:
        logger.error(f"Ошибка при инициализации файла администраторов: {e}")
    
    # При запуске отправляем меню администраторам 1-го уровня
    for user_id in ALLOWED_USERS:
        try:
            await bot.send_message(
                chat_id=user_id,
                text="VPN-бот запущен! Используйте /admin для доступа к панели администратора или /connect для подключения к микротику."
            )
        except Exception as e:
            logger.error(f"Не удалось отправить приветствие пользователю {user_id}: {e}")

    logger.info("Бот начал работу")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)