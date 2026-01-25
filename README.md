<div align="center">
  <a href="https://v2.nonebot.dev/store"><img src="https://nonebot.dev/logo.png" width="180" height="180" alt="NoneBotPluginLogo"></a>
  <br>
  <h1>nonebot-plugin-qqmusic-reco</h1>
</div>

<div align="center">
_🎵 基于QQ音乐歌单的音乐推荐 ✨_
_基于QQ音乐歌单，支持多群配置、持久化管理及定时自定义话术的音乐推荐插件_

<a href="https://pypi.python.org/pypi/nonebot-plugin-qqmusic-reco">
  <img src="https://img.shields.io/pypi/v/nonebot-plugin-qqmusic-reco.svg" alt="pypi">
</a>
<img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="python">
<img src="https://img.shields.io/badge/nonebot2-v2.0.0+-green.svg" alt="nonebot2">
<a href="https://github.com/ChlorophyTeio/nonebot-plugin-qqmusic-reco/blob/main/LICENSE">
  <img src="https://img.shields.io/github/license/ChlorophyTeio/nonebot-plugin-qqmusic-reco.svg" alt="license">
</a>

## 📖 简介

这是一个适用于 NoneBot2 的音乐推荐插件。它允许你配置多个 QQ 音乐歌单（支持权重分配），并根据设定的时间（Cron 表达式或间隔）向不同的群组推送随机音乐。

### ✨ 核心特性

- **多群独立配置**：每个群可以订阅不同的歌单配置、设置不同的推送时间。
- **灵活的定时任务**：支持 `cron`（指定时间点，如 8点、12点半）和 `interval`（间隔分钟）两种模式。
- **自定义话术系统**：支持按时间段（如早安/晚安）配置不同的开场白。
- **不太健壮的配置管理**：: (
- **权重随机算法**：支持在一个配置中混合多个歌单，并按权重抽取歌曲。

## 💿 安装

<details>
<summary>使用 nb-cli 安装（推荐）</summary>

```bash
nb plugin install nonebot-plugin-qqmusic-reco

```

<details>
<summary>使用 pip 安装</summary>

```bash
pip install nonebot-plugin-qqmusic-reco

```

## ⚙️ 配置 (没啥用)

在 `.env` 文件中配置全局参数。大多数功能可通过指令动态配置，以下为默认值：

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `qqmusic_priority` | int | 5 | 插件响应优先级 |
| `qqmusic_block` | bool | True | 是否阻断后续指令 |
| `qqmusic_output_n` | int | 3 | 默认每次推荐歌曲数量 |
| `qqmusic_max_pool` | int | 200 | 获取歌单时的最大歌曲池大小（防止内存溢出） |
| `qqmusic_cute_message` | bool | True | 是否开启推送时的卖萌话术 |
| `LOG_LEVEL` | str | INFO | 调试时可设为 DEBUG 查看详细任务添加日志 |

## 💻 指令使用

### 基础指令

* **`reco list`**
* 查看当前所有可用的推荐配置（歌单集合）。


* **`reco now [数量]`**
* 立即在当前群发送推荐（默认 3 首）。
* 示例：`reco now 5`


* **`reco help`**
* 查看帮助菜单。



### 管理员指令 (SUPERUSER)

#### 1. 创建推荐配置 (Create)

将一个或多个歌单打包为一个“推荐配置”。

```bash
reco create <名称> <歌单链接 或 权重|ID>

```

* **简单模式**：`reco create 抖音热歌 https://y.qq.com/n/ryqq/playlist/xxxx`
* **混合模式（支持权重）**：
`reco create 混合歌单 2.0|7671500210,1.0|862300123`
*(表示 2.0 权重的歌单 ID 和 1.0 权重的歌单 ID 混合)*

#### 2. 删除推荐配置 (Del)

```bash
reco del <名称>

```

#### 3. 订阅推送 (Sub)

**注意**：为了防止误操作，如果该群已订阅，需先使用 `reco td` 取消订阅。

```bash
reco sub <配置名> <定时规则> [每次数量]

```

**定时规则格式说明**：

* **Cron 模式 (推荐)**：使用 `cron:` 前缀（可省略），后跟时间点。支持英文或中文逗号。
* `8` -> 每天 08:00
* `8,12,18` -> 每天 08:00, 12:00, 18:00
* `8:30,20,0` -> 每天 08:30, 20:00, 00:00


* **间隔模式**：使用 `interval:` 前缀，后跟分钟数。
* `interval:60` -> 每 60 分钟推送一次



**示例**：

```bash
# 每天 8点、12点、18点 推送 "抖音热歌" 配置，每次 3 首
reco sub 抖音热歌 8,12,18 3

# 每天 13:45 和 22:00 推送
reco sub Default 13:45,22:00 5

```

#### 4. 取消订阅 (Unsub)

```bash
reco td
# 或
reco unsub

```

#### 5. 重载配置 (Reload)

强制从磁盘重新加载配置文件并刷新定时任务（通常用于手动修改 JSON 文件后）。

```bash
reco reload

```

## 📂 数据与自定义

插件数据存储在 `nonebot-plugin-localstore` 定义的数据目录中。

### 1. 目录结构

```text
data/
└── nonebot_plugin_qqmusic_reco/
    ├── reco_config.json    # 推荐歌单配置
    ├── group_config.json   # 群订阅配置
    └── cute_messages.json  # 自定义话术配置

```

### 2. 自定义话术 (cute_messages.json)

你可以编辑 `cute_messages.json` 来定制不同时间段的提示语。

* 支持跨天时间段（如 `22:00` 到 `06:00`）。
* Bot 启动时会自动加载，或使用 `reco reload` 刷新。

**格式示例**：

```json
[
  {
    "start_time": "06:00", 
    "end_time": "10:59", 
    "messages": [
      "早安喵~ 又是元气满满的一天！", 
      "太阳晒屁股啦，听首歌醒醒脑吧~"
    ]
  },
  {
    "start_time": "22:00", 
    "end_time": "05:59", 
    "messages": [
      "夜深了，来点助眠音乐吗？", 
      "还不睡？那就陪我听首歌吧~"
    ]
  }
]

```

## ❓ 常见问题 (FAQ)

**Q: 定时任务设置了 13:45，但实际上等到晚上才推送？**
A: 请检查你的服务器/容器时区。

* 插件启动时会在日志打印 `[QQMusicReco] ... 当前系统时间: xxxx`。
* 如果时间与北京时间不符，请调整 Docker 容器时区（挂载 `/etc/localtime`）。

**Q: 输入 `reco sub` 提示“本群已订阅”？**
A: 这是为了防止误覆盖原有配置。请先发送 `reco td` 取消当前订阅，再重新设置。

**Q: 为什么我看不到详细的任务添加日志？**
A: 从 `v0.1.16` 开始，详细的任务添加日志已降级为 `DEBUG` 等级。如果需要排查，请在 `.env` 中设置 `LOG_LEVEL=DEBUG`。

## 📝 依赖库

* [nonebot-plugin-apscheduler](https://github.com/nonebot/plugin-apscheduler) - 定时任务管理
* [nonebot-plugin-localstore](https://github.com/nonebot/plugin-localstore) - 本地数据存储
* `httpx` - 网络请求

## 🤝 贡献

欢迎提交 Issue 或 Pull Request！
