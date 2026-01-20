from pydantic import BaseModel
from typing import Optional


class Config(BaseModel):
    qqmusic_priority: int = 5
    qqmusic_block: bool = True
    qqmusic_max_pool: int = 200
    qqmusic_output_n: int = 3
    qqmusic_seed: Optional[int] = None
    qqmusic_custom_message: bool = True