import asyncio

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.resource.download_all_resource import download_all_resource

sv_download_config = SV("ww资源下载", pm=1)


@sv_download_config.on_fullmatch(("强制下载全部资源", "下载全部资源", "补充资源", "刷新补充资源"))
async def send_download_resource_msg(bot: Bot, ev: Event):
    await bot.send("[鸣潮] 正在开始下载~可能需要较久的时间!")
    await download_all_resource(force="强制" in ev.raw_text)
    await bot.send("[鸣潮] 下载完成！")


async def startup():
    logger.info("[鸣潮] 等待资源下载完成...")
    await download_all_resource()
    logger.info("[鸣潮] 资源下载完成！完成启动！")
