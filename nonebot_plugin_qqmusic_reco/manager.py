import json
import random
from typing import Dict, List, Union, Any, Optional
from datetime import datetime, time
from pydantic import BaseModel
from nonebot import logger
import nonebot_plugin_localstore as store
from pathlib import Path


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
        # 获取当前插件的数据目录
        self.data_dir = store.get_plugin_data_dir()

        # 拼接文件路径
        self.reco_file = self.data_dir / "reco_config.json"
        self.group_file = self.data_dir / "group_config.json"
        self.cute_file = self.data_dir / "cute_messages.json"

        self.reco_data: Dict[str, RecoItem] = {}
        self.group_data: Dict[str, GroupSettings] = {}
        self.cute_config: list = []

        self.load_all()

    def load_cute_messages(self) -> list:
        if not self.cute_file.exists():
            return []
        try:
            with open(self.cute_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[QQMusicReco] 加载自定义话术失败: {e}")
            return []

    def load_all(self):
        # 1. 加载推荐配置
        if not self.reco_file.exists():
            init_reco = {
                "Default": {
                    "creator": None,
                    "playlists": ["https://y.qq.com/n/ryqq_v2/playlist/7671500210|1"],
                }
            }
            self._save_json(self.reco_file, init_reco)

        try:
            with open(self.reco_file, "r", encoding="utf-8") as f:
                raw_reco = json.load(f)
                self.reco_data = {k: RecoItem(**v) for k, v in raw_reco.items()}
        except Exception as e:
            logger.error(f"[QQMusicReco] ❌ 加载推荐配置(reco_config.json)失败: {e}。将保留内存中的旧配置。")
            # 不进行重置，防止文件损坏导致数据清空

        # 2. 加载群订阅配置
        if not self.group_file.exists():
            self._save_json(self.group_file, {})

        try:
            with open(self.group_file, "r", encoding="utf-8") as f:
                raw_group = json.load(f)
                self.group_data = {gid: GroupSettings(**s) for gid, s in raw_group.items()}
        except Exception as e:
            logger.error(f"[QQMusicReco] ❌ 加载群配置(group_config.json)失败: {e}。将保留内存中的旧配置。")
            # 不进行重置

        # 3. 加载自定义话术
        self.cute_config = self.load_cute_messages()
        logger.info(f"[QQMusicReco] 配置加载完成: {len(self.group_data)} 个群订阅, {len(self.reco_data)} 个推荐单。")

    def _save_json(self, file_path, data):
        def to_dict(obj):
            if hasattr(obj, "model_dump"): return obj.model_dump()
            if hasattr(obj, "dict"): return obj.dict()
            return obj

        serializable = {k: to_dict(v) for k, v in data.items()}
        file_path.parent.mkdir(parents=True, exist_ok=True)

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
        if not is_admin and item.creator and item.creator != str(user_id):
            return f"❌ 推荐名 '{name}' 由 {item.creator} 创建，你无权删除。"
        del self.reco_data[name]
        self.save_reco()
        return f"✅ 已删除推荐配置: {name}"

    def pick_cute_message(self, now: datetime = None) -> Optional[str]:
        """根据当前时间段选择并随机返回一条话术"""
        if not self.cute_config:
            self.cute_config = self.load_cute_messages()
            if not self.cute_config:
                return None

        if now is None:
            now = datetime.now()
        now_time = now.time()

        candidates = []
        for item in self.cute_config:
            try:
                st = time.fromisoformat(item["start_time"])
                et = time.fromisoformat(item["end_time"])
                in_range = False
                if st <= et:
                    in_range = st <= now_time < et
                else:
                    # 跨天
                    in_range = now_time >= st or now_time < et

                if in_range:
                    candidates.extend(item.get("messages", []))
            except Exception as e:
                logger.warning(f"[QQMusicReco] 话术时间解析错误: {e}")

        if candidates:
            return random.choice(candidates)
        return None


manager = ConfigManager()