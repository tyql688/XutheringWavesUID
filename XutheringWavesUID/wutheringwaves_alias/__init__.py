import re

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.name_convert import load_alias_data
from .char_alias_ops import action_char_alias, char_alias_list
from ..utils.char_info_utils import PATTERN

sv_add_char_alias = SV("ww角色名别名", pm=0)
sv_list_char_alias = SV("ww角色名别名列表")


@sv_add_char_alias.on_regex(
    rf"^(?P<action>添加|删除)(?P<name>{PATTERN})别名(?P<new_alias>{PATTERN})$",
    block=True,
)
async def handle_add_char_alias(bot: Bot, ev: Event):
    action = ev.regex_dict.get("action")
    char_name = ev.regex_dict.get("name")
    new_alias = ev.regex_dict.get("new_alias")
    if not char_name or not new_alias:
        return await bot.send("角色名或别名不能为空")

    msg = await action_char_alias(action, char_name, new_alias)
    if "成功" in msg:
        load_alias_data()
    await bot.send(msg)


@sv_list_char_alias.on_regex(rf"^(?P<name>{PATTERN})别名(列表)?$", block=True)
async def handle_list_char_alias(bot: Bot, ev: Event):
    char_name = ev.regex_dict.get("name")
    if not char_name:
        return await bot.send("角色名不能为空")
    char_name = char_name.strip()
    msg = await char_alias_list(char_name)
    await bot.send(msg)
