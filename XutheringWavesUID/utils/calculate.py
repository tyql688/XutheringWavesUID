from typing import Any, Dict, List, Optional, Tuple, Union


def calc_phantom_entry(
    index: int,
    prop: Any,
    cost: int,
    calc_temp: Optional[Dict],
    attribute_name: str,
) -> Tuple[float, float]:
    from .waves_build.calculate import calc_phantom_entry as _func

    return _func(index, prop, cost, calc_temp, attribute_name)


def calc_phantom_score(
    role_id: Union[str, int],
    props: List[Any],
    cost: int,
    calc_temp: Optional[Dict],
) -> Tuple[float, str]:
    from .waves_build.calculate import calc_phantom_score as _func

    return _func(role_id, props, cost, calc_temp)


def get_calc_map(
    phantom_card: Dict,
    role_name: str,
    role_id: Union[str, int],
) -> Dict:
    from .waves_build.calculate import get_calc_map as _func

    return _func(phantom_card, role_name, role_id)


def get_max_score(
    cost: int,
    calc_temp: Optional[Dict],
) -> Tuple[float, Any]:
    from .waves_build.calculate import get_max_score as _func

    return _func(cost, calc_temp)


def get_total_score_bg(
    char_name: str,
    score: float,
    calc_temp: Optional[Dict],
) -> str:
    from .waves_build.calculate import get_total_score_bg as _func

    return _func(char_name, score, calc_temp)


def get_valid_color(
    name: str,
    value: Union[str, float],
    calc_temp: Optional[Dict],
) -> Tuple[str, str]:
    from .waves_build.calculate import get_valid_color as _func

    return _func(name, value, calc_temp)


# try:
#     from .waves_build.calculate import *
# except ImportError:
#     logger.warning("无法导入 calculate，将尝试下载")
