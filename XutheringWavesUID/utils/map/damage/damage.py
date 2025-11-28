def check_if_ph_3(ph_name: str, ph_num: int, check_name: str) -> bool:
    from ..waves_build.damage import check_if_ph_3 as _func

    return _func(ph_name, ph_num, check_name)


def check_if_ph_5(ph_name: str, ph_num: int, check_name: str) -> bool:
    from ..waves_build.damage import check_if_ph_5 as _func

    return _func(ph_name, ph_num, check_name)


# try:
#     from ..waves_build.damage import *
# except ImportError:
#     logger.warning("无法导入 damage，将尝试下载")
