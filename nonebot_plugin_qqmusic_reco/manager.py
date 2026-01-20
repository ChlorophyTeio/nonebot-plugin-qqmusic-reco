import json
import random
from typing import Dict, List, Union, Any, Optional
from datetime import datetime, time
from pydantic import BaseModel
from nonebot import logger
import nonebot_plugin_localstore as store
from pathlib import Path

# --- 最佳实践：在模块级别获取数据目录 ---
# 修复：使用 get_data_dir 并显式传入插件名
# 这样可以确保在任何上下文（包括测试环境）下都能正确获取路径
PLUGIN_NAME = "nonebot_plugin_qqmusic_reco"
DATA_DIR = store.get_data_dir(PLUGIN_NAME)

RECO_FILE = DATA_DIR / "reco_config.json"
GROUP_FILE = DATA_DIR / "group_config.json"
CUTE_FILE = DATA_DIR / "cute_messages.json"

# 确保存储目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)


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
        # 直接使用模块级别的路径常量
        self.reco_file = RECO_FILE
        self.group_file = GROUP_FILE
        self.cute_file = CUTE_FILE

        self.reco_data: Dict[str, RecoItem] = {}
        self.group_data: Dict[str, GroupSettings] = {}
        self.cute_config: list = []

        self.load_all()

    def load_cute_messages(self) -> list:
        """加载自定义话术，如果文件不存在则生成默认模板"""
        if not self.cute_file.exists():
            # 这里定义默认模板，用户可以在生成后修改 json 文件实现完全自定义
            default_template = [
                {
                    "start_time": "06:00",
                    "end_time": "11:00",
                    "messages": [
                        "早安喵！新的一天也要元气满满哦~",
                        "早起的鸟儿有歌听~",
                    ],
                },
                {
                    "start_time": "11:00",
                    "end_time": "14:00",
                    "messages": [
                        "午饭时间到！来点音乐下饭吧~",
                        "午休时间，听首歌放松一下？",
                    ],
                },
                {
                    "start_time": "22:00",
                    "end_time": "02:00",
                    "messages": ["夜深了，来首助眠曲吧~", "还不睡是在等我的推荐吗？"],
                },
                {
                    "start_time": "02:00",
                    "end_time": "06:00",
                    "messages": ["熬夜对身体不好哦，听完这首快睡吧！"],
                },
            ]
            self._save_json(self.cute_file, default_template)
            return default_template

        try:
            with open(self.cute_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载可爱话术失败: {e}")
            # 如果加载失败，返回空列表，避免报错，bot 依然可以运行（只是不发话术）
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
            logger.error(f"加载推荐配置失败: {e}")
            self.reco_data = {}

        # 2. 加载群订阅配置
        if not self.group_file.exists():
            self._save_json(self.group_file, {})

        try:
            with open(self.group_file, "r", encoding="utf-8") as f:
                raw_group = json.load(f)
                self.group_data = {
                    gid: GroupSettings(**s) for gid, s in raw_group.items()
                }
        except Exception as e:
            logger.error(f"加载群配置失败: {e}")
            self.group_data = {}

        # 3. 加载可爱话术
        self.cute_config = self.load_cute_messages()

    def _save_json(self, file_path: Path, data):
        def to_dict(obj):
            if hasattr(obj, "model_dump"):
                return obj.model_dump()
            if hasattr(obj, "dict"):
                return obj.dict()
            return obj

        if isinstance(data, list):
            serializable = [to_dict(item) for item in data]
        else:
            serializable = {k: to_dict(v) for k, v in data.items()}

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
        # 简单权限校验
        if not is_admin and item.creator and item.creator != str(user_id):
            return f"❌ 推荐名 '{name}' 由 {item.creator} 创建，你无权删除。"
        del self.reco_data[name]
        self.save_reco()
        return f"✅ 已删除推荐配置: {name}"

    def pick_cute_message(self, now: datetime = None) -> Optional[str]:
        """根据当前时间段选择并随机返回一条话术"""
        if not self.cute_config:
            # 尝试重新加载，防止是初始化后用户修改了文件
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
                # 判断当前时间是否在区间内 (支持跨天)
                in_range = False
                if st <= et:
                    in_range = st <= now_time < et
                else:
                    # 跨天，例如 22:00 到 06:00
                    in_range = now_time >= st or now_time < et

                if in_range:
                    candidates.extend(item.get("messages", []))
            except Exception as e:
                logger.warning(f"Cute message config parsing error: {e}")

        if candidates:
            return random.choice(candidates)
        return None


manager = ConfigManager()
