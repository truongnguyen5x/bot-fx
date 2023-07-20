import os

os.system("mongodump --out ~/mongo-backup")
os.system("zip -r ~/backup.zip ~/mongo-backup/*")
