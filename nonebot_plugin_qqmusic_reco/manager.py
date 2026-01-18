import json
from typing import Dict, List, Union, Any, Optional
from pydantic import BaseModel
import nonebot_plugin_localstore as store
from nonebot import logger

import random
from datetime import datetime, time
from pathlib import Path


# 读取本地话术配置（localstore路径）
def load_cute_messages(cute_file=None):
    if cute_file is None:
        # 默认用localstore路径
        import nonebot_plugin_localstore as store
        cute_file = store.get_plugin_data_file("cute_messages.json")
    if not cute_file.exists():
        return []
    with open(cute_file, "r", encoding="utf-8") as f:
        return json.load(f)

# 根据当前时间段选择并随机返回一条话术
def pick_cute_message(now: datetime = None, cute_config=None, cute_file=None) -> Optional[str]:
    if cute_config is None:
        cute_config = load_cute_messages(cute_file)
    if now is None:
        now = datetime.now()
    now_time = now.time()
    candidates = []
    for item in cute_config:
        try:
            st = time.fromisoformat(item["start_time"])
            et = time.fromisoformat(item["end_time"])
            # 支持跨天时间段
            if st <= et:
                if st <= now_time < et:
                    candidates.extend(item["messages"])
            else:
                if now_time >= st or now_time < et:
                    candidates.extend(item["messages"])
        except Exception as e:
            logger.warning(f"Cute message config error: {e}")
    if candidates:
        return random.choice(candidates)
    return None


class RecoItem(BaseModel):
    creator: Optional[str] = None
    playlists: List[Union[str, Dict[str, Any]]]


class GroupSettings(BaseModel):
    group_id: str
    enable: bool = True
    reco_name: str = "Default"
    timer_mode: str = "cron"
    timer_value: str = "8,10,12,14,18,22,0"
    output_n: int = 3


class ConfigManager:
    def __init__(self):
        self.reco_file = store.get_plugin_data_file("reco_config.json")
        self.group_file = store.get_plugin_data_file("group_config.json")
        self.cute_file = store.get_plugin_data_file("cute_messages.json")
        self.reco_data: Dict[str, RecoItem] = {}
        self.group_data: Dict[str, GroupSettings] = {}
        self.cute_config: list = []
        self.load_all()

    def load_all(self):
        # 加载推荐配置
        if not self.reco_file.exists():
            init_reco = {
                "Default": {
                    "creator": None,
                    "playlists": ["https://y.qq.com/n/ryqq_v2/playlist/7671500210|1"],
                }
            }
            self._save_json(self.reco_file, init_reco)

        with open(self.reco_file, "r", encoding="utf-8") as f:
            raw_reco = json.load(f)
            self.reco_data = {k: RecoItem(**v) for k, v in raw_reco.items()}


        # 加载群订阅配置
        if not self.group_file.exists():
            self._save_json(self.group_file, {})
        with open(self.group_file, "r", encoding="utf-8") as f:
            raw_group = json.load(f)
            self.group_data = {gid: GroupSettings(**s) for gid, s in raw_group.items()}

        # 加载可爱话术配置
        self.cute_config = load_cute_messages(self.cute_file)

    def _save_json(self, file_path, data):
        serializable = {
            k: (v.dict() if hasattr(v, "dict") else v) for k, v in data.items()
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)

    def save_reco(self):
        self._save_json(self.reco_file, self.reco_data)

    def save_group(self):
        self._save_json(self.group_file, self.group_data)

    def add_reco(self, name: str, playlists: List[str], creator: str):
        if name in self.reco_data:
            return False
        self.reco_data[name] = RecoItem(creator=creator, playlists=playlists)
        self.save_reco()
        return True

    def del_reco(self, name: str, user_id: str, is_admin: bool):
        if name not in self.reco_data:
            return "❌ 未找到该推荐名。"
        item = self.reco_data[name]
        if is_admin or item.creator and item.creator != str(user_id):
            return f"❌ 推荐名 '{name}' 由 {item.creator} 创建，你无权删除。"
        del self.reco_data[name]
        self.save_reco()
        return f"✅ 已删除推荐配置: {name}"


manager = ConfigManager()
