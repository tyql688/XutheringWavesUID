from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
import shutil
import os
import hashlib
from pathlib import Path

from ..utils.resource.download_all_resource import (download_all_resource, reload_all_modules, BUILD_PATH, BUILD_TEMP, MAP_BUILD_PATH, MAP_BUILD_TEMP)


def get_dir_hash(dir_path):
    """用于比较内容是否相同"""
    if not os.path.exists(dir_path):
        return ""

    hash_md5 = hashlib.md5()

    for filepath in sorted(Path(dir_path).rglob('*')):
        if filepath.is_file():
            with open(filepath, 'rb') as f:
                hash_md5.update(f.read())
            hash_md5.update(str(filepath.relative_to(dir_path)).encode())

    return hash_md5.hexdigest()


def copy_if_different(src, dst, name):
    """比较两个目录的内容哈希值，仅在不同时复制"""
    src_hash = get_dir_hash(src)
    dst_hash = get_dir_hash(dst)

    if src_hash != dst_hash:
        logger.info(f"[鸣潮] {name} 内容不同，开始更新...")
        shutil.copytree(src, dst, dirs_exist_ok=True)
        logger.info(f"[鸣潮] {name} 更新完成！")
    else:
        logger.debug(f"[鸣潮] {name} 内容相同，无需更新")

sv_download_config = SV("ww资源下载", pm=1)


@sv_download_config.on_fullmatch(("强制下载全部资源", "下载全部资源", "补充资源", "刷新补充资源"))
async def send_download_resource_msg(bot: Bot, ev: Event):
    await bot.send("[鸣潮] 正在开始下载~可能需要较久的时间！请勿重复执行！")
    await download_all_resource(force="强制" in ev.raw_text)
    copy_if_different(BUILD_TEMP, BUILD_PATH, "安全工具资源")
    copy_if_different(MAP_BUILD_TEMP, MAP_BUILD_PATH, "伤害计算资源")
    reload_all_modules()
    await bot.send("[鸣潮] 下载完成！")


async def startup():
    logger.info("[鸣潮] 等待资源下载完成...")
    await download_all_resource()
    copy_if_different(BUILD_TEMP, BUILD_PATH, "安全工具资源")
    copy_if_different(MAP_BUILD_TEMP, MAP_BUILD_PATH, "伤害计算资源")
    reload_all_modules()
    logger.info("[鸣潮] 资源下载完成！完成启动！")
