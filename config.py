import json
import os

# Проверяем наличие директории data
if not os.path.exists('data'):
    os.makedirs('data', exist_ok=True)

# Проверяем наличие конфигурационных файлов
if not os.path.exists("data/mikrotiks.json"):
    with open("data/mikrotiks.json", 'w', encoding='utf-8') as f:
        json.dump({"mikrotiks": []}, f, indent=2)

if not os.path.exists("data/admins.json"):
    with open("data/admins.json", 'w', encoding='utf-8') as f:
        json.dump({"level_1": [], "level_2": []}, f, indent=2)

# Загружаем данные из config.json
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BOT_TOKEN = config["bot_token"]
ALLOWED_USERS = config["allowed_users"]
ALLOWED_GROUPS = config["allowed_groups"]