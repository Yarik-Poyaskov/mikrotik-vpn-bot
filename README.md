# MikroTik VPN Control Bot

Telegram бот для управления VPN подключениями через MikroTik API с поддержкой OpenVPN и WireGuard.

## Возможности

- Управление профилями OpenVPN
- Управление пиров WireGuard  
- Поддержка множественных MikroTik устройств
- Двухуровневая система администрирования
- Генерация конфигурационных файлов и QR-кодов
- Загрузка пользовательских шаблонов OpenVPN

## Установка

### Через Docker (рекомендуется)

1. Клонируйте репозиторий:
```bash
git clone https://github.com/ваш-username/mikrotik-vpn-bot.git
cd mikrotik-vpn-bot

Скопируйте и настройте конфигурацию:

bashcp config.json.example config.json

Отредактируйте config.json - укажите токен бота и ID администраторов
Запустите через Docker Compose:

bashdocker-compose up -d
Ручная установка

Установите зависимости:

bashpip install -r requirements.txt

Настройте конфигурацию в config.json
Запустите бота:

bashpython main.py
Конфигурация
config.json
json{
  "bot_token": "ВАШ_ТОКЕН_БОТА",
  "allowed_users": [ВАШ_TELEGRAM_ID],
  "allowed_groups": []
}
Структура данных
Данные о микротиках и администраторах хранятся в JSON файлах:

data/mikrotiks.json - конфигурация MikroTik устройств
data/admins.json - администраторы и их права

Использование

Запустите бота командой /start
Используйте /admin для доступа к панели администратора (только для админов 1-го уровня)
Добавьте MikroTik устройства через админ-панель
Выберите устройство командой /connect
Используйте основное меню для управления VPN

Команды

/start - Запуск бота
/admin - Панель администратора
/connect - Выбор MikroTik устройства
/status - Активные VPN подключения
/profile - Список профилей OpenVPN
/add_profile - Добавить профиль OpenVPN
/wg_status - Список пиров WireGuard
/add_wg - Добавить пир WireGuard