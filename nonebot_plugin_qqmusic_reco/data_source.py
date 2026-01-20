import re
import random
import httpx
from typing import List, Dict, Any, Optional, Union
from .config import Config

PLAYLIST_ID_RE = re.compile(r"/playlist/(\d{5,})|disstid=(\d{5,})|id=(\d{5,})")

class QQMusicReco:
    def __init__(self, config: Config):
        self.global_cfg = config
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36", 
            "Referer": "https://y.qq.com/",
            "Accept": "application/json"
        }

    def _extract_id(self, p: str) -> Optional[str]:
        p = str(p).strip()
        if re.fullmatch(r"\d{5,}", p): return p
        m = PLAYLIST_ID_RE.search(p)
        return next((g for g in m.groups() if g), None) if m else None

    async def fetch_playlist(self, disstid: str) -> List[Dict]:
        url = "https://c.y.qq.com/qzone/fcg-bin/fcg_ucc_getcdinfo_byids_cp.fcg"
        params = {
            "type": 1, "json": 1, "utf8": 1, "disstid": disstid,
            "format": "json", "g_tk": 5381, "platform": "yqq"
        }
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                cdlist = data.get("cdlist", [])
                if cdlist and cdlist[0].get("songlist"):
                    return cdlist[0]["songlist"]
                return []
        except Exception:
            return []

    async def get_recommendation(self, playlists: List[Union[str, Dict]], output_n: int = 3) -> str:
        # 设置随机种子
        if self.global_cfg.qqmusic_seed is not None:
            random.seed(self.global_cfg.qqmusic_seed)
        else:
            random.seed() 

        all_songs = []
        weights_map = {}

        # 1. 解析歌单并获取歌曲
        for raw in playlists:
            weight, p_str = 1.0, ""
            if isinstance(raw, dict):
                weight = float(raw.get("weight", 1.0))
                p_str = str(raw.get("id") or raw.get("url") or "")
            else:
                p_str = str(raw)
                if "|" in p_str:
                    parts = p_str.rsplit("|", 1)
                    p_str = parts[0]
                    try: 
                        weight = float(parts[1])
                    except ValueError: 
                        weight = 1.0
            
            disstid = self._extract_id(p_str)
            if disstid:
                weights_map[disstid] = weight
                songs = await self.fetch_playlist(disstid)
                for s in songs:
                    s["source_id"] = disstid
                    all_songs.append(s)

        if not all_songs: 
            return "❌ 无法获取歌曲数据，请检查歌单配置。"

        # 2. 池化与截断
        pool = all_songs
        max_pool = self.global_cfg.qqmusic_max_pool
        if len(pool) > max_pool:
            random.shuffle(pool)
            pool = pool[:max_pool]

        # 3. 按来源分组以便加权抽取
        by_pid = {}
        for s in pool:
            pid = s["source_id"]
            by_pid.setdefault(pid, []).append(s)

        picked = []
        # 过滤掉权重为0或者没有获取到歌曲的歌单ID
        pids = [p for p in by_pid.keys() if weights_map.get(p, 1.0) > 0]
        
        if not pids: 
            return "❌ 有效歌单为空。"

        final_output_n = max(1, min(output_n, len(pool)))
        
        # 4. 加权随机抽取
        for _ in range(final_output_n):
            # 动态计算当前还有剩余歌曲的歌单及其权重
            live_options = [(p, weights_map.get(p, 1.0)) for p in pids if by_pid.get(p)]
            if not live_options: 
                break
            
            lpids, lweights = zip(*live_options)
            target_pid = random.choices(lpids, weights=lweights, k=1)[0]
            
            # 从选中歌单随机取一首并移除（防止重复）
            target_list = by_pid[target_pid]
            picked_song = target_list.pop(random.randrange(len(target_list)))
            picked.append(picked_song)

        # 5. 格式化输出 (移除标题行)
        res = []
        for i, s in enumerate(picked, 1):
            singers = " / ".join([str(si.get("name", "未知")) for si in s.get("singer", [])])
            song_name = s.get('songname', '未知曲目')
            mid = s.get('songmid', '')
            link = f"https://y.qq.com/n/ryqq/songDetail/{mid}" if mid else "无需链接"
            
            res.append(f"{i}. {song_name} - {singers}")
            res.append(f"   {link}")
        
        return "\n".join(res)