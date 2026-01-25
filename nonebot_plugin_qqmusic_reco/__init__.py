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
    extra={
        "author": "ChlorophyTeio",
        "version": "0.1.14"
    }
)


# --- 定时任务逻辑 ---
def refresh_jobs():
    for job in scheduler.get_jobs():
        if job.id.startswith("reco_push_"): job.remove()

    for gid, setting in manager.group_data.items():
        if not setting.enable:
            continue
        if setting.timer_mode == "cron":
            # 支持 timer_value: "8,12,16:30,20,0"
            time_points = [t.strip() for t in str(setting.timer_value).split(",") if t.strip()]
            for idx, t in enumerate(time_points):
                if ":" in t:
                    hour, minute = t.split(":", 1)
                    try:
                        hour = int(hour)
                        minute = int(minute)
                    except Exception:
                        logger.warning(f"定时配置格式错误: {t}")
                        continue
                else:
                    try:
                        hour = int(t)
                        minute = 0
                    except Exception:
                        logger.warning(f"定时配置格式错误: {t}")
                        continue

                async def push(g_id=gid, h=hour, m=minute):
                    s = manager.group_data.get(g_id)
                    if not s:
                        return
                    cute_msg = None
                    if config.qqmusic_cute_message and s.timer_mode == "cron":
                        from .manager import pick_cute_message
                        from datetime import datetime, time as dtime
                        now = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
                        cute_msg = pick_cute_message(now=now)
                    if cute_msg:
                        await_msg = cute_msg
                    else:
                        await_msg = "让我思考一下推荐什么喵..."
                    for bot in get_bots().values():
                        try:
                            await bot.send_group_msg(group_id=int(g_id), message=await_msg)
                        except Exception:
                            pass
                    msg = await reco_service.get_recommendation(manager.reco_data.get(s.reco_name).playlists,
                                                                s.output_n)
                    for bot in get_bots().values():
                        try:
                            await bot.send_group_msg(group_id=int(g_id), message=msg)
                        except Exception:
                            pass

                scheduler.add_job(
                    push,
                    id=f"reco_push_{gid}_{idx}",
                    trigger="cron",
                    hour=hour,
                    minute=minute,
                    misfire_grace_time=60
                )
        else:
            # interval 模式保持原样
            try:
                minutes = int(setting.timer_value)
            except Exception:
                logger.warning(f"interval 配置格式错误: {setting.timer_value}")
                continue

            async def push(g_id=gid):
                s = manager.group_data.get(g_id)
                if not s:
                    return
                cute_msg = None
                if config.qqmusic_cute_message and s.timer_mode == "cron":
                    from .manager import pick_cute_message
                    cute_msg = pick_cute_message()
                if cute_msg:
                    await_msg = cute_msg
                else:
                    await_msg = "让我思考一下推荐什么喵..."
                for bot in get_bots().values():
                    try:
                        await bot.send_group_msg(group_id=int(g_id), message=await_msg)
                    except Exception:
                        pass
                msg = await reco_service.get_recommendation(manager.reco_data.get(s.reco_name).playlists, s.output_n)
                for bot in get_bots().values():
                    try:
                        await bot.send_group_msg(group_id=int(g_id), message=msg)
                    except Exception:
                        pass

            scheduler.add_job(
                push,
                id=f"reco_push_{gid}",
                trigger="interval",
                minutes=minutes,
                misfire_grace_time=60
            )


get_driver().on_startup(refresh_jobs)

# --- 指令处理 ---
reco_cmd = on_command("reco", priority=config.qqmusic_priority, block=config.qqmusic_block)


@reco_cmd.handle()
async def _(bot: Bot, event: MessageEvent, arg: Message = CommandArg()):
    msg_txt = arg.extract_plain_text().strip().split()
    if not msg_txt: await reco_cmd.finish("请输入指令参数，或发送 reco help")

    sub_cmd = msg_txt[0].lower()
    user_id = str(event.user_id)
    is_su = await SUPERUSER(bot, event)

    # 1. reco now [N]
    if sub_cmd == "now":
        # 指令触发，始终用固定话术
        await reco_cmd.send("让我思考一下推荐什么喵...")
        count = int(msg_txt[1]) if len(msg_txt) > 1 and msg_txt[1].isdigit() else config.qqmusic_output_n
        reco_name = "Default"
        if isinstance(event, GroupMessageEvent):
            g_set = manager.group_data.get(str(event.group_id))
            if g_set: reco_name = g_set.reco_name
        playlists = manager.reco_data.get(reco_name).playlists if reco_name in manager.reco_data else manager.reco_data[
            "Default"].playlists
        res = await reco_service.get_recommendation(playlists, count)
        await reco_cmd.finish(res)

    # 2. reco reload (SUPERUSER ONLY)
    elif sub_cmd == "reload":
        if not is_su: await reco_cmd.finish("⛔ 权限不足：仅限 SUPERUSER 使用。")
        manager.load_all();
        refresh_jobs()
        await reco_cmd.finish("✅ 配置已重载，定时任务已刷新。")

    # 3. reco sub <推荐名> <模式:时间> <数量> (SUPERUSER ONLY)
    elif sub_cmd == "sub":
        if not is_su:
            await reco_cmd.finish("⛔ 权限不足：仅限 SUPERUSER 使用。")
        if not isinstance(event, GroupMessageEvent):
            await reco_cmd.finish("❌ 请在群聊中使用此指令。")

        gid = str(event.group_id)

        # --- 新增校验逻辑 ---
        if gid in manager.group_data:
            await reco_cmd.finish("⚠️ 本群已订阅，请使用 reco td 或 reco unsub 取消订阅后再重新设置。")
        # ------------------

        name = msg_txt[1] if len(msg_txt) > 1 else "Default"
        timer = msg_txt[2] if len(msg_txt) > 2 else "cron:8,12,18"
        num = int(msg_txt[3]) if len(msg_txt) > 3 and msg_txt[3].isdigit() else 3

        mode, val = timer.split(":", 1) if ":" in timer else ("cron", timer)

        # 检查推荐配置是否存在
        if name not in manager.reco_data:
            await reco_cmd.finish(f"❌ 推荐配置 '{name}' 不存在，请先使用 reco create 创建。")

        manager.group_data[gid] = GroupSettings(
            group_id=gid, reco_name=name, timer_mode=mode, timer_value=val, output_n=num
        )
        manager.save_group()
        refresh_jobs()
        await reco_cmd.finish(f"✅ 订阅成功！\n推荐配置：{name}\n定时：{mode}({val})\n每轮数量：{num}")

    # 4. reco unsub / td
    elif sub_cmd in ["unsub", "td"]:
        gid = str(event.group_id)
        if gid in manager.group_data:
            del manager.group_data[gid];
            manager.save_group();
            refresh_jobs()
            await reco_cmd.finish("✅ 已取消本群订阅。")
        await reco_cmd.finish("❌ 本群尚未订阅。")

    # 5. reco create <名> <列表>
    elif sub_cmd == "create":
        if len(msg_txt) < 3: await reco_cmd.finish("❌ 格式：reco create <名称> <URL|权,ID|权...>")
        name, content = msg_txt[1], msg_txt[2].split(",")
        if manager.add_reco(name, content, user_id):
            await reco_cmd.finish(f"✅ 推荐配置 '{name}' 已创建。")
        await reco_cmd.finish(f"❌ 推荐名 '{name}' 已存在。")

    # 6. reco del <名>
    elif sub_cmd == "del":
        if len(msg_txt) < 2: await reco_cmd.finish("❌ 格式：reco del <名称>")
        res = manager.del_reco(msg_txt[1], user_id, is_su)
        await reco_cmd.finish(res)

    # 7. reco list / help
    elif sub_cmd == "list":
        await reco_cmd.finish("📜 可用推荐列表：\n" + "\n".join(
            [f"- {k} (创建者:{v.creator or 'admin'})" for k, v in manager.reco_data.items()]))

    elif sub_cmd == "help":
        await reco_cmd.finish(
            "🎵 QQ音乐推荐指令帮助：\n"
            "reco now [数量] - 立即推荐\n"
            "reco list - 查看所有推荐配置\n"
            "reco create <名> <链|权,ID|权> - 创建配置\n"
            "reco del <名> - 删除自己创建的配置\n"
            "reco td/unsub - 取消订阅本群\n"
            "--- 管理员指令 ---\n"
            "reco sub <名> <模式:时间> <数量> - 订阅本群\n"
            "reco reload - 强制重载配置"
        )
