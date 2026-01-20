from nonebot import on_command, require, get_bots, get_plugin_config, logger, get_driver
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Bot, Message, GroupMessageEvent, MessageEvent
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER

require("nonebot_plugin_apscheduler")
require("nonebot_plugin_localstore")
from nonebot_plugin_apscheduler import scheduler

from .config import Config
from .data_source import QQMusicReco
from .manager import manager, GroupSettings

config = get_plugin_config(Config)
reco_service = QQMusicReco(config)

__plugin_meta__ = PluginMetadata(
    name="基于QQ音乐歌单的音乐推荐",
    description="基于QQ音乐歌单，支持多群配置、持久化管理及定时自定义话术的音乐推荐插件",
    usage="""指令列表：
- reco now [数量] : 立即推荐
- reco list : 查看可用配置
- reco create <名> <URL> : 创建配置
- reco sub <名> <时间> [数量] : (管理员) 订阅定时推送
- reco reload : (管理员) 重载配置""",
    type="application",
    homepage="https://github.com/ChlorophyTeio/nonebot-plugin-qqmusic-reco",
    config=Config,
    supported_adapters={"~onebot.v11"},
    extra={"author": "ChlorophyTeio", "version": "0.1.9"},
)


# --- 核心推送逻辑 ---
async def run_push_task(group_id: str, hour: int = None, minute: int = None):
    """独立的推送任务执行函数"""
    setting = manager.group_data.get(group_id)
    if not setting or not setting.enable:
        return

    # 1. 准备话术
    await_msg = "让我思考一下推荐什么喵..."
    if (
        config.qqmusic_cute_message
        and setting.timer_mode == "cron"
        and hour is not None
    ):
        from datetime import datetime

        # 构造一个当天的对应时间用于判断
        now = datetime.now().replace(hour=hour, minute=minute or 0, second=0)

        # 重新加载一次话术配置，允许用户热更新json文件而不必重启bot
        manager.cute_config = manager.load_cute_messages()

        cute = manager.pick_cute_message(now=now)
        if cute:
            await_msg = cute

    # 2. 获取推荐内容
    reco_conf = manager.reco_data.get(setting.reco_name)
    if not reco_conf:
        logger.warning(
            f"Group {group_id} uses unknown reco config: {setting.reco_name}"
        )
        return

    music_msg = await reco_service.get_recommendation(
        reco_conf.playlists, setting.output_n
    )

    # 3. 发送消息 (遍历 Bot 直到发送成功，避免重复)
    bots = get_bots()
    sent = False
    for bot in bots.values():
        try:
            # 先发提示语
            await bot.send_group_msg(group_id=int(group_id), message=await_msg)
            # 再发歌单
            await bot.send_group_msg(group_id=int(group_id), message=music_msg)
            sent = True
            break  # 发送成功一个 Bot 就退出
        except Exception as e:
            logger.debug(f"Bot {bot.self_id} failed to send to group {group_id}: {e}")
            continue

    if not sent:
        logger.warning(f"所有 Bot 均无法向群 {group_id} 发送消息。")


# --- 定时任务管理 ---
def refresh_jobs():
    # 清理旧任务
    for job in scheduler.get_jobs():
        if job.id.startswith("reco_push_"):
            job.remove()

    logger.info("Refreshing QQMusic Reco jobs...")

    for gid, setting in manager.group_data.items():
        if not setting.enable:
            continue

        if setting.timer_mode == "cron":
            # 解析 cron 时间字符串 "8,12:30,18"
            time_points = [
                t.strip() for t in str(setting.timer_value).split(",") if t.strip()
            ]
            for idx, t in enumerate(time_points):
                h, m = 0, 0
                try:
                    if ":" in t:
                        h_str, m_str = t.split(":", 1)
                        h, m = int(h_str), int(m_str)
                    else:
                        h = int(t)
                except ValueError:
                    logger.warning(f"群 {gid} 定时配置格式错误: {t}")
                    continue

                # 添加 Cron 任务
                scheduler.add_job(
                    run_push_task,
                    "cron",
                    id=f"reco_push_{gid}_{idx}",
                    hour=h,
                    minute=m,
                    kwargs={"group_id": gid, "hour": h, "minute": m},
                    misfire_grace_time=60,
                )

        elif setting.timer_mode == "interval":
            # 添加 Interval 任务
            try:
                minutes = int(setting.timer_value)
                scheduler.add_job(
                    run_push_task,
                    "interval",
                    id=f"reco_push_{gid}",
                    minutes=minutes,
                    kwargs={"group_id": gid},
                    misfire_grace_time=60,
                )
            except ValueError:
                logger.warning(f"群 {gid} Interval 配置格式错误: {setting.timer_value}")


get_driver().on_startup(refresh_jobs)

# --- 指令处理 ---
reco_cmd = on_command(
    "reco", priority=config.qqmusic_priority, block=config.qqmusic_block
)


@reco_cmd.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    msg_txt = arg.extract_plain_text().strip().split()
    if not msg_txt:
        await reco_cmd.finish("请输入指令参数，或发送 reco help")

    sub_cmd = msg_txt[0].lower()
    user_id = str(event.user_id)
    is_su = await SUPERUSER(bot, event)

    # 1. reco now [N]
    if sub_cmd == "now":
        # 立即指令不使用时间段话术，使用通用话术
        await reco_cmd.send("让我思考一下推荐什么喵...")

        count = config.qqmusic_output_n
        if len(msg_txt) > 1 and msg_txt[1].isdigit():
            count = int(msg_txt[1])

        reco_name = "Default"
        if isinstance(event, GroupMessageEvent):
            g_set = manager.group_data.get(str(event.group_id))
            if g_set:
                reco_name = g_set.reco_name

        reco_item = manager.reco_data.get(reco_name)
        if not reco_item:
            reco_item = manager.reco_data.get("Default")

        if not reco_item:
            await reco_cmd.finish("❌ 未找到推荐配置，请检查 Default 配置。")

        res = await reco_service.get_recommendation(reco_item.playlists, count)
        await reco_cmd.finish(res)

    # 2. reco reload (SUPERUSER ONLY)
    elif sub_cmd == "reload":
        if not is_su:
            await reco_cmd.finish("⛔ 权限不足：仅限 SUPERUSER 使用。")
        manager.load_all()
        refresh_jobs()
        await reco_cmd.finish("✅ 配置已重载，定时任务已刷新。")

    # 3. reco sub <推荐名> <模式:时间> <数量> (SUPERUSER ONLY)
    elif sub_cmd == "sub":
        if not is_su:
            await reco_cmd.finish("⛔ 权限不足：仅限 SUPERUSER 使用。")
        if not isinstance(event, GroupMessageEvent):
            await reco_cmd.finish("❌ 请在群聊中使用此指令。")

        name = msg_txt[1] if len(msg_txt) > 1 else "Default"
        if name not in manager.reco_data:
            await reco_cmd.finish(
                f"❌ 推荐配置 '{name}' 不存在，请先使用 reco list 查看。"
            )

        timer = msg_txt[2] if len(msg_txt) > 2 else "cron:8,12,18"
        num = int(msg_txt[3]) if len(msg_txt) > 3 and msg_txt[3].isdigit() else 3

        mode, val = timer.split(":", 1) if ":" in timer else ("cron", timer)

        manager.group_data[str(event.group_id)] = GroupSettings(
            group_id=str(event.group_id),
            reco_name=name,
            timer_mode=mode,
            timer_value=val,
            output_n=num,
        )
        manager.save_group()
        refresh_jobs()
        await reco_cmd.finish(
            f"✅ 订阅成功！\n推荐配置：{name}\n定时：{mode} ({val})\n每轮数量：{num}"
        )

    # 4. reco unsub / td
    elif sub_cmd in ["unsub", "td"]:
        gid = str(event.group_id) if isinstance(event, GroupMessageEvent) else None
        if gid and gid in manager.group_data:
            del manager.group_data[gid]
            manager.save_group()
            refresh_jobs()
            await reco_cmd.finish("✅ 已取消本群订阅。")
        await reco_cmd.finish("❌ 本群尚未订阅。")

    # 5. reco create <名> <列表>
    elif sub_cmd == "create":
        if len(msg_txt) < 3:
            await reco_cmd.finish("❌ 格式：reco create <名称> <URL|权,ID|权...>")
        name, content_str = msg_txt[1], msg_txt[2]
        content_list = content_str.split(",")
        if manager.add_reco(name, content_list, user_id):
            await reco_cmd.finish(f"✅ 推荐配置 '{name}' 已创建。")
        await reco_cmd.finish(f"❌ 推荐名 '{name}' 已存在。")

    # 6. reco del <名>
    elif sub_cmd == "del":
        if len(msg_txt) < 2:
            await reco_cmd.finish("❌ 格式：reco del <名称>")
        res = manager.del_reco(msg_txt[1], user_id, is_su)
        await reco_cmd.finish(res)

    # 7. reco list / help
    elif sub_cmd == "list":
        lines = ["📜 可用推荐列表："]
        for k, v in manager.reco_data.items():
            lines.append(f"- {k} (创建者: {v.creator or 'System'})")
        await reco_cmd.finish("\n".join(lines))

    elif sub_cmd == "help":
        await reco_cmd.finish(
            "QQ音乐推荐指令帮助：\n"
            "reco now [数量] - 立即推荐\n"
            "reco list - 查看所有推荐配置\n"
            "reco create <名> <链|权,ID|权> - 创建配置\n"
            "reco del <名> - 删除自己创建的配置\n"
            "reco td/unsub - 取消订阅本群\n"
            "--- 管理员指令 ---\n"
            "reco sub <名> <模式:时间> <数量> - 订阅本群\n"
            "reco reload - 强制重载配置"
        )
