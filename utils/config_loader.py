# utils/config_loader.py
import os
import yaml
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def load_yaml(file_name):
    """读取 config 目录下的 YAML 配置文件"""
    path = os.path.join("config", file_name)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def get_feishu_webhook():
    """从环境变量获取飞书 Webhook 地址"""
    return os.getenv("FEISHU_WEBHOOK", "")