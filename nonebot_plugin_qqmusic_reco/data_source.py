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
            "User-Agent": "Mozilla/5.0", 
            "Referer": "https://y.qq.com/",
            "Accept": "application/json,text/plain,*/*"
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
                return cdlist[0].get("songlist", []) if cdlist else []
        except Exception:
            return []

    async def get_recommendation(self, playlists: List[Union[str, Dict]], output_n: int = 3) -> str:
        if self.global_cfg.qqmusic_seed is not None:
            random.seed(self.global_cfg.qqmusic_seed)
        else:
            random.seed() 

        all_songs = []
        weights_map = {}

        for raw in playlists:
            weight, p = 1.0, ""
            if isinstance(raw, dict):
                weight = float(raw.get("weight", 1.0))
                p = str(raw.get("id") or raw.get("url") or "")
            else:
                p = str(raw)
                if "|" in p:
                    p, w = p.rsplit("|", 1)
                    try: weight = float(w)
                    except: weight = 1.0
            
            disstid = self._extract_id(p)
            if disstid:
                weights_map[disstid] = weight
                songs = await self.fetch_playlist(disstid)
                for s in songs:
                    s["source_id"] = disstid
                    all_songs.append(s)

        if not all_songs: return "❌ 无法获取歌曲数据，请检查歌单配置。"

        pool = all_songs
        max_pool = self.global_cfg.qqmusic_max_pool
        if len(pool) > max_pool:
            random.shuffle(pool)
            pool = pool[:max_pool]

        by_pid = {}
        for s in pool:
            pid = s["source_id"]
            by_pid.setdefault(pid, []).append(s)

        picked = []
        pids = [p for p in by_pid.keys() if weights_map.get(p, 1.0) > 0]
        weights = [weights_map.get(p, 1.0) for p in pids]

        if not pids: return "❌ 有效歌单为空。"

        final_output_n = max(1, min(output_n, len(pool)))
        
        for _ in range(final_output_n):
            live = [(p, w) for p, w in zip(pids, weights) if by_pid.get(p)]
            if not live: break
            lpids, lweights = zip(*live)
            target_pid = random.choices(lpids, weights=lweights, k=1)[0]
            # 这里的 pop 可能会报错如果列表空了，虽然 live 检查了，但还是加个保险
            if not by_pid[target_pid]: continue
            picked.append(by_pid[target_pid].pop(random.randrange(len(by_pid[target_pid]))))

        res = ["YLSの音乐推荐\n"]
        for i, s in enumerate(picked, 1):
            singers = " / ".join([str(si.get("name", "未知")) for si in s.get("singer", [])])
            res.append(f"{i}. {s.get('songname')} - {singers}")
            res.append(f"   https://y.qq.com/n/ryqq/songDetail/{s.get('songmid')}\n")
        return "\n".join(res)