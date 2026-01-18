# Copilot Instructions for nonebot-plugin-qqmusic-reco

## 项目架构与主要组件
- 本插件基于 [NoneBot2](https://v2.nonebot.dev/) 框架，适配 OneBot v11 协议。
- 主要目录结构：
  - `__init__.py`：插件入口，注册命令、调度任务，初始化配置与服务。
  - `config.py`：定义插件配置项（如推荐数量、优先级、可爱消息开关等）。
  - `data_source.py`：核心业务逻辑，负责与 QQ 音乐 API 交互，获取歌单、推荐歌曲。
  - `manager.py`：群组配置与可爱消息管理，支持多群自定义推送时间、消息内容。
  - `cute_messages.json`：可爱消息配置，按时间段随机推送。

## 关键开发模式与约定
- **定时任务**：使用 `nonebot_plugin_apscheduler`，通过 `refresh_jobs()` 动态注册/移除群推送任务。
- **多群配置**：`manager.group_data` 保存每个群的推送设置（启用/禁用、定时模式、时间等）。
- **可爱消息**：通过 `manager.py` 的 `pick_cute_message`，按时间段和权重随机选取。
- **配置获取**：统一通过 `get_plugin_config(Config)` 获取，避免硬编码。
- **外部依赖**：需安装 `nonebot_plugin_apscheduler`、`nonebot_plugin_localstore`、`httpx`、`pydantic`。

## 常用开发/调试流程
- **本地调试**：推荐用 `nonebot2` 官方文档方式运行，插件无需特殊 build 步骤。
- **配置修改**：如需更改推送策略、消息内容，优先修改 `config.py` 或 `cute_messages.json`，重载插件后生效。
- **日志**：统一用 `nonebot.logger` 输出，便于排查。
- **命令入口**：所有用户命令均以 `reco` 开头，详见 `usage` 字段。

## 代码风格与扩展建议
- 遵循 NoneBot2 插件开发规范，类型注解齐全，配置项集中于 `Config`。
- 新增功能建议以“服务类”方式扩展（如 `QQMusicReco`），便于测试与复用。
- 群组相关数据建议通过 `manager.py` 统一管理，避免分散。

## 参考文件
- 插件主入口：[nonebot_plugin_qqmusic_reco/__init__.py](nonebot_plugin_qqmusic_reco/__init__.py)
- 配置定义：[nonebot_plugin_qqmusic_reco/config.py](nonebot_plugin_qqmusic_reco/config.py)
- 数据源与业务逻辑：[nonebot_plugin_qqmusic_reco/data_source.py](nonebot_plugin_qqmusic_reco/data_source.py)
- 群组与消息管理：[nonebot_plugin_qqmusic_reco/manager.py](nonebot_plugin_qqmusic_reco/manager.py)

---
如需补充特殊约定或遇到不明确的开发场景，请在此文档下方补充说明。