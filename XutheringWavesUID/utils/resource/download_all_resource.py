import os
import sys
import platform

from gsuid_core.logger import logger
from gsuid_core.utils.download_resource.download_core import download_all_file

from .RESOURCE_PATH import (
    MAP_PATH,
    BUILD_PATH,
    BUILD_TEMP,
    AVATAR_PATH,
    WEAPON_PATH,
    PHANTOM_PATH,
    ROLE_BG_PATH,
    MAP_CHAR_PATH,
    MATERIAL_PATH,
    SHARE_BG_PATH,
    MAP_ALIAS_PATH,
    MAP_BUILD_PATH,
    MAP_BUILD_TEMP,
    ROLE_PILE_PATH,
    XFM_GUIDE_PATH,
    XMU_GUIDE_PATH,
    MAP_DETAIL_PATH,
    WUHEN_GUIDE_PATH,
    JIEXING_GUIDE_PATH,
    MAP_CHALLENGE_PATH,
    XIAOYANG_GUIDE_PATH,
    JINLINGZI_GUIDE_PATH,
    MOEALKYNE_GUIDE_PATH,
    ROLE_DETAIL_SKILL_PATH,
    ROLE_DETAIL_CHAINS_PATH,
)


def get_target_package():
    system = sys.platform
    machine = platform.machine().lower()

    py_ver = f"py{sys.version_info.major}.{sys.version_info.minor}"

    if py_ver not in ["py3.10", "py3.11", "py3.12", "py3.13"]:
        logger.error(f"不支持的Python版本: {py_ver}")
        return ""

    if system == "win32":
        if "64" in machine:
            return f"win-x86_64-{py_ver}"
        else:
            logger.error("暂不支持32位Windows")
            return ""

    elif system == "linux":
        if "x86_64" in machine:
            return f"linux-x86_64-{py_ver}"
        elif "aarch64" in machine:
            return f"linux-aarch64-{py_ver}"
        else:
            logger.error("暂不支持非x86_64架构的Linux")

    is_android = "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ
    if is_android:
        if py_ver == "py3.12":
            return "android-aarch64-ndk"
        else:
            logger.error("安卓环境仅支持Python 3.12")
            return f"linux-x86_64-{py_ver}"

    elif system == "darwin":
        if "arm64" in machine:
            return f"macos-arm64-{py_ver}"
        elif "x86_64" in machine:
            logger.error("暂不支持Intel架构的Mac")
            return ""

    logger.error(f"不支持的操作系统: {system} {machine}")
    return f"linux-x86_64-{py_ver}"


PLATFORM = get_target_package()


async def download_all_resource(force: bool = False):
    if force:
        import shutil

        shutil.rmtree(BUILD_TEMP, ignore_errors=True)
        shutil.rmtree(MAP_BUILD_TEMP, ignore_errors=True)
        BUILD_TEMP.mkdir(parents=True, exist_ok=True)
        MAP_BUILD_TEMP.mkdir(parents=True, exist_ok=True)

    await download_all_file(
        "XutheringWavesUID",
        {
            "resource/avatar": AVATAR_PATH,
            "resource/weapon": WEAPON_PATH,
            "resource/role_pile": ROLE_PILE_PATH,
            "resource/role_bg": ROLE_BG_PATH,
            "resource/role_detail/skill": ROLE_DETAIL_SKILL_PATH,
            "resource/role_detail/chains": ROLE_DETAIL_CHAINS_PATH,
            "resource/share": SHARE_BG_PATH,
            "resource/phantom": PHANTOM_PATH,
            "resource/material": MATERIAL_PATH,
            "resource/guide/XMu": XMU_GUIDE_PATH,
            "resource/guide/Moealkyne": MOEALKYNE_GUIDE_PATH,
            "resource/guide/JinLingZi": JINLINGZI_GUIDE_PATH,
            "resource/guide/JieXing": JIEXING_GUIDE_PATH,
            "resource/guide/XiaoYang": XIAOYANG_GUIDE_PATH,
            "resource/guide/WuHen": WUHEN_GUIDE_PATH,
            "resource/guide/XFM": XFM_GUIDE_PATH,
            f"resource/build/{PLATFORM}/waves_build": BUILD_TEMP,
            f"resource/build/{PLATFORM}/map/waves_build": MAP_BUILD_TEMP,
            "resource/map": MAP_PATH,
            "resource/map/character": MAP_CHAR_PATH,
            "resource/map/detail_json": MAP_DETAIL_PATH,
            "resource/map/detail_json/challenge": MAP_CHALLENGE_PATH,
            "resource/map/alias": MAP_ALIAS_PATH,
        },
        "https://ww.loping151.top",
        "小维资源",
    )

    if "win" in PLATFORM:
        logger.warning(
            "如下载失败原因为 Permission Denied, 请手动删除 ./XutheringWavesUID/utils/waves_build 和 ./XutheringWavesUID/utils/map/waves_build 文件夹后重试，或尝试 强制下载全部资源"
        )

def reload_all_modules():
    from ..safety import reload_safety_module
    from ..calculate import reload_calculate_module

    # 强制加载所有 map 数据
    from ..name_convert import ensure_data_loaded as ensure_name_convert_loaded
    from ..ascension.char import ensure_data_loaded as ensure_char_loaded
    from ..ascension.echo import ensure_data_loaded as ensure_echo_loaded
    from ..ascension.sonata import ensure_data_loaded as ensure_sonata_loaded
    from ..ascension.weapon import ensure_data_loaded as ensure_weapon_loaded
    from ..map.damage.damage import reload_damage_module
    from ..map.damage.register import reload_all_register

    # no async
    reload_calculate_module()
    reload_safety_module()
    reload_damage_module()
    reload_all_register()

    # 在下载完成后强制加载所有数据
    ensure_name_convert_loaded(force=True)
    ensure_char_loaded(force=True)
    ensure_weapon_loaded(force=True)
    ensure_echo_loaded(force=True)
    ensure_sonata_loaded(force=True)
