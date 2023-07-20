import os
import requests
from dotenv import load_dotenv

load_dotenv()

os.system("mongodump --out ~/mongo-backup")
os.system("zip -r ~/backup.zip ~/mongo-backup/*")


files = {"document": open("/root/backup.zip", "rb")}
requests.post(
    f'https://api.telegram.org/bot{os.getenv("TELEGRAM_BOT_TOKEN")}/sendDocument',
    data={
        "chat_id": os.getenv("TELEGRAM_USER_ID"),
        "parse_mode": "HTML",
        "caption": "backup DB",
    },
    files=files,
    stream=True,
)

