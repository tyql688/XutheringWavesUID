import re

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..wutheringwaves_develop.develop import calc_develop_cost
from ..utils.char_info_utils import PATTERN

role_develop = SV("waves角色培养")


@role_develop.on_regex(
    rf"^(?P<develop_list>({PATTERN})(?:\s+{PATTERN})*?)\s*(?:养成|培养|培养成本)$",
    block=True,
)
async def calc_develop(bot: Bot, ev: Event):
    develop_list_str = ev.regex_dict.get("develop_list", "")
    develop_list = develop_list_str.split()
    logger.info(f"养成列表: {develop_list}")

    develop_cost = await calc_develop_cost(ev, develop_list)
    if isinstance(develop_cost, (str, bytes)):
        return await bot.send(develop_cost)