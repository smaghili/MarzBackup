import os
import json

CONFIG_FILE = 'config.json'

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    else:
        default_config = {
            "API_TOKEN": "",  # توکن ربات تلگرام
            "ADMIN_CHAT_ID": "",  # شناسه چت ادمین
            "backup_interval_minutes": None,  # فاصله زمانی پشتیبان‌گیری
            "db_password": None,  # پسورد دیتابیس
            "admins": []  # لیست برای ذخیره شناسه‌های ادمین
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
