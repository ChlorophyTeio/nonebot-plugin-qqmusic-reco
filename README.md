<!-- markdownlint-disable MD041 -->
<p align="center">
  <a href="https://nonebot.dev/"><img src="https://nonebot.dev/logo.png" width="200" height="200" alt="nonebot"></a>
</p>

<div align="center">

# nonebot-plugin-qqmusic-reco

_🎵 QQ音乐多群定时推荐插件，支持自定义话术与灵活推送配置 ✨_

</div>

<p align="center">
  <a href="https://github.com/ChlorophyTeio/nonebot-plugin-qqmusic-reco/blob/main/LICENSE">
    <img src="https://img.shields.io/github/license/ChlorophyTeio/nonebot-plugin-qqmusic-reco.svg" alt="license">
  </a>
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">
  <img src="https://img.shields.io/badge/nonebot2-v2-green.svg" alt="nonebot2">
</p>

## 关于插件

适用于 NoneBot2 的 QQ 音乐推荐插件，支持多群定时推送、自定义话术、灵活配置，数据源为 QQ 音乐歌单。

## 安装

推荐使用 nb-cli 安装：

```bash
nb plugin install nonebot-plugin-qqmusic-reco
```

或使用 pip：

```bash
pip install nonebot-plugin-qqmusic-reco
```

## 快速开始

1. 在 NoneBot2 项目中使用 env 配置 (全部不建议配置，配置应当前往各个模块的JSON)：

```
qqmusic_priority=5
qqmusic_block=True
qqmusic_max_pool=200
qqmusic_output_n=3
qqmusic_seed=114514
qqmusic_cute_message=True
```

2. 配置推荐推送：

- 指令：
  - `reco sub <推荐名> <模式:时间> <数量>` 订阅本群推荐
  - `reco td` 或 `reco unsub` 取消订阅
  - `reco create <名> <歌单URL,...>` 新建推荐配置
  - `reco del <名>` 删除推荐配置
  - `reco now [数量]` 立即获取推荐
  - `reco list` 查看所有推荐配置
  - `reco help` 查看帮助

## 配置说明

- 推荐推送时间支持“8,12,16:30,20”格式，分钟可自定义
- 自定义话术配置存放于 localstore 数据目录的 `cute_messages.json`，格式示例：

```json
[
  {"start_time": "08:00", "end_time": "11:00", "messages": ["早上好喵，今天推荐...", "喵呜，清晨的歌单来啦~"]},
  {"start_time": "16:00", "end_time": "22:00", "messages": ["晚上好喵，来点音乐放松一下吧~"]}
]
```

- 其他配置项详见 `config.py`，如推荐数量、优先级等

## 数据存储

插件所有数据（推荐配置、群组配置、自定义话术）均存放于 localstore 数据目录，支持跨平台。

## 依赖

- nonebot2 >= 2.0.0
- nonebot_plugin_apscheduler
- nonebot_plugin_localstore
- httpx
- pydantic

## 贡献与反馈

欢迎 issue、PR 或讨论！

## FAQ

- Q: 如何自定义话术？
  A: 编辑 localstore 数据目录下的 cute_messages.json，格式见上。
- Q: 如何设置多时段推送？
  A: 在群配置的 timer_value 中填写多个时间点，支持“小时:分钟”以及““小时”格式。
---

详细用法与高级配置请见源码及注释。
