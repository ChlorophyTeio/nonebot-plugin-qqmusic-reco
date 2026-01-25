from nonebot import on_command, require, get_bots, get_plugin_config, logger, get_driver
from nonebot.plugin import PluginMetadata
from nonebot.adapters.onebot.v11 import Bot, Message, GroupMessageEvent, MessageEvent
from nonebot.params import CommandArg
from nonebot.permission import SUPERUSER
from datetime import datetime

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
        "version": "0.1.15"
    }
)


# --- 定时任务逻辑 ---
def refresh_jobs():
    # [修改点 1] 降级为 DEBUG：详细的开始时间和系统时间只在调试时需要
    logger.debug(f"[QQMusicReco] 正在刷新定时任务... 当前系统时间: {datetime.now()}")

    # 1. 清理旧任务
    removed_count = 0
    for job in scheduler.get_jobs():
        if job.id.startswith("reco_push_"):
            job.remove()
            removed_count += 1

    if removed_count > 0:
        # 保持 DEBUG
        logger.debug(f"[QQMusicReco] 已清理 {removed_count} 个旧定时任务")

    # 2. 添加新任务
    count_added = 0
    for gid, setting in manager.group_data.items():
        if not setting.enable:
            continue

        if setting.timer_mode == "cron":
            # 支持 timer_value: "8,12,16:30,20,0"
            raw_times = str(setting.timer_value).replace("，", ",")  # 兼容中文逗号
            time_points = [t.strip() for t in raw_times.split(",") if t.strip()]

            for idx, t in enumerate(time_points):
                try:
                    if ":" in t:
                        hour_str, minute_str = t.split(":", 1)
                        hour = int(hour_str)
                        minute = int(minute_str)
                    else:
                        hour = int(t)
                        minute = 0
                except ValueError:
                    logger.error(f"[QQMusicReco] 群 {gid} 定时格式错误: '{t}'，已跳过")
                    continue

                # 使用闭包参数锁定变量 h=hour, m=minute
                async def push(g_id=gid, h=hour, m=minute):
                    s = manager.group_data.get(g_id)
                    if not s: return

                    # 获取可爱文案
                    cute_msg = None
                    if config.qqmusic_cute_message:
                        try:
                            # 构造当前触发的时间点用于判断文案区间
                            now_trigger = datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)
                            cute_msg = manager.pick_cute_message(now=now_trigger)
                        except Exception as e:
                            logger.warning(f"[QQMusicReco] 获取文案失败: {e}")

                    await_msg = cute_msg if cute_msg else "让我思考一下推荐什么喵..."

                    bots = get_bots()
                    if not bots:
                        logger.warning(f"[QQMusicReco] 定时任务触发(群{g_id})，但没有连接的 Bot")
                        return

                    for bot in bots.values():
                        try:
                            # 1. 发送提示语
                            await bot.send_group_msg(group_id=int(g_id), message=await_msg)

                            # 2. 获取并发送歌曲
                            reco_config = manager.reco_data.get(s.reco_name)
                            if not reco_config:
                                await bot.send_group_msg(group_id=int(g_id), message=f"❌ 找不到推荐配置: {s.reco_name}")
                                return

                            msg = await reco_service.get_recommendation(reco_config.playlists, s.output_n)
                            await bot.send_group_msg(group_id=int(g_id), message=msg)
                            logger.info(f"[QQMusicReco] 群 {g_id} 定时推送 ({h:02d}:{m:02d}) 完成")
                        except Exception as e:
                            logger.warning(f"[QQMusicReco] 群 {g_id} 推送异常: {e}")

                job_id = f"reco_push_{gid}_{idx}"
                scheduler.add_job(
                    push,
                    id=job_id,
                    trigger="cron",
                    hour=hour,
                    minute=minute,
                    misfire_grace_time=60
                )
                count_added += 1
                # [修改点 2] 降级为 DEBUG：每个任务的添加细节只在调试时查看
                logger.debug(f"[QQMusicReco] 添加任务: 群[{gid}] 时间[{hour:02d}:{minute:02d}] ID[{job_id}]")

        else:
            # interval 模式
            try:
                minutes = int(setting.timer_value)
            except Exception:
                logger.warning(f"interval 配置格式错误: {setting.timer_value}")
                continue

            async def push_interval(g_id=gid):
                s = manager.group_data.get(g_id)
                if not s: return

                cute_msg = manager.pick_cute_message() if config.qqmusic_cute_message else None
                await_msg = cute_msg if cute_msg else "让我思考一下推荐什么喵..."

                bots = get_bots()
                for bot in bots.values():
                    try:
                        await bot.send_group_msg(group_id=int(g_id), message=await_msg)
                        reco_config = manager.reco_data.get(s.reco_name)
                        if reco_config:
                            msg = await reco_service.get_recommendation(reco_config.playlists, s.output_n)
                            await bot.send_group_msg(group_id=int(g_id), message=msg)
                    except Exception:
                        pass

            scheduler.add_job(
                push_interval,
                id=f"reco_push_{gid}",
                trigger="interval",
                minutes=minutes,
                misfire_grace_time=60
            )
            count_added += 1

    # [保持点] 这个是 INFO，符合你的要求（保留总结性日志）
    logger.info(f"[QQMusicReco] 定时任务加载完毕，共 {count_added} 个任务。")


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
        await reco_cmd.send("让我思考一下推荐什么喵...")
        count = int(msg_txt[1]) if len(msg_txt) > 1 and msg_txt[1].isdigit() else config.qqmusic_output_n
        reco_name = "Default"
        if isinstance(event, GroupMessageEvent):
            g_set = manager.group_data.get(str(event.group_id))
            if g_set: reco_name = g_set.reco_name

        target_reco = manager.reco_data.get(reco_name)
        # 如果找不到群配置的名称，回退到 Default
        if not target_reco and "Default" in manager.reco_data:
            target_reco = manager.reco_data["Default"]

        if not target_reco:
            await reco_cmd.finish("❌ 没有任何可用的推荐配置。")

        res = await reco_service.get_recommendation(target_reco.playlists, count)
        await reco_cmd.finish(res)

    # 2. reco reload (SUPERUSER ONLY)
    elif sub_cmd == "reload":
        if not is_su: await reco_cmd.finish("⛔ 权限不足：仅限 SUPERUSER 使用。")
        manager.load_all()
        refresh_jobs()
        await reco_cmd.finish("✅ 配置已重载，定时任务已刷新。")

    # 3. reco sub <推荐名> <模式:时间> <数量> (SUPERUSER ONLY)
    elif sub_cmd == "sub":
        if not is_su:
            await reco_cmd.finish("⛔ 权限不足：仅限 SUPERUSER 使用。")
        if not isinstance(event, GroupMessageEvent):
            await reco_cmd.finish("❌ 请在群聊中使用此指令。")

        gid = str(event.group_id)

        # --- 校验逻辑：防止重复覆盖 ---
        if gid in manager.group_data:
            await reco_cmd.finish("⚠️ 本群已订阅，请使用 reco td 或 reco unsub 取消订阅后再重新设置。")

        name = msg_txt[1] if len(msg_txt) > 1 else "Default"
        timer = msg_txt[2] if len(msg_txt) > 2 else "cron:8,12,18"
        num = int(msg_txt[3]) if len(msg_txt) > 3 and msg_txt[3].isdigit() else 3

        mode, val = timer.split(":", 1) if ":" in timer else ("cron", timer)

        # 检查推荐配置是否存在
        if name not in manager.reco_data:
            await reco_cmd.finish(
                f"❌ 推荐配置 '{name}' 不存在，请先使用 reco create 创建。\n可用列表: {', '.join(manager.reco_data.keys())}")

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
            del manager.group_data[gid]
            manager.save_group()
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