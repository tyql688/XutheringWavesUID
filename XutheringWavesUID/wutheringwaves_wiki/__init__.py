import re

from gsuid_core.bot import Bot
from gsuid_core.models import Event
from gsuid_core.sv import SV

from ..utils.name_convert import char_name_to_char_id
from ..utils.char_info_utils import PATTERN
from .draw_char import draw_char_wiki
from .draw_echo import draw_wiki_echo
from .draw_list import draw_sonata_list, draw_weapon_list
from .draw_weapon import draw_wiki_weapon
from .guide import get_guide
from .draw_tower import draw_tower_challenge_img, draw_slash_challenge_img

sv_waves_guide = SV("鸣潮攻略")
sv_waves_wiki = SV("鸣潮wiki")
sv_waves_tower = SV("waves查询深塔信息", priority=4)
sv_waves_slash_info = SV("waves查询海墟信息", priority=4)


@sv_waves_guide.on_regex(
    rf"^(?P<wiki_name>{PATTERN})(?P<wiki_type>共鸣链|命座|天赋|技能|图鉴|wiki|介绍)$",
    block=True,
)
async def send_waves_wiki(bot: Bot, ev: Event):
    wiki_name = ev.regex_dict.get("wiki_name", "")
    wiki_type = ev.regex_dict.get("wiki_type", "")

    at_sender = True if ev.group_id else False
    if wiki_type in ("共鸣链", "命座", "天赋", "技能"):
        char_name = wiki_name
        char_id = char_name_to_char_id(char_name)
        if not char_id:
            msg = f"[鸣潮] wiki【{char_name}】无法找到, 可能暂未适配, 请先检查输入是否正确！\n"
            return await bot.send(msg, at_sender)

        query_role_type = (
            "天赋" if "技能" in wiki_type or "天赋" in wiki_type else "命座"
        )
        img = await draw_char_wiki(char_id, query_role_type)
        if isinstance(img, str):
            msg = f"[鸣潮] wiki【{wiki_name}】无法找到, 可能暂未适配, 请先检查输入是否正确！\n"
            return await bot.send(msg, at_sender)
        await bot.send(img)
    else:
        img = await draw_wiki_weapon(wiki_name)
        if isinstance(img, str) or not img:
            echo_name = wiki_name
            await bot.logger.info(f"[鸣潮] 开始获取{echo_name}wiki")
            img = await draw_wiki_echo(echo_name)

        if isinstance(img, str) or not img:
            msg = f"[鸣潮] wiki【{wiki_name}】无法找到, 可能暂未适配, 请先检查输入是否正确！\n"
            return await bot.send(msg, at_sender)

        await bot.send(img)


@sv_waves_guide.on_regex(rf"^(?P<char>{PATTERN})攻略$", block=True)
async def send_role_guide_pic(bot: Bot, ev: Event):
    char_name = ev.regex_dict.get("char", "")

    char_id = char_name_to_char_id(char_name)
    at_sender = True if ev.group_id else False
    if not char_id:
        msg = f"[鸣潮] 角色名【{char_name}】无法找到, 可能暂未适配, 请先检查输入是否正确！\n"
        return await bot.send(msg, at_sender)

    await get_guide(bot, ev, char_name)


@sv_waves_guide.on_regex(rf"^(?P<type>{PATTERN})?武器(?:列表)?$", block=True)
async def send_weapon_list(bot: Bot, ev: Event):
    weapon_type = ev.regex_dict.get("type", "")
    img = await draw_weapon_list(weapon_type)
    await bot.send(img)


@sv_waves_guide.on_regex(r".*套装(列表)?$", block=True)
async def send_sonata_list(bot: Bot, ev: Event):
    await bot.send(await draw_sonata_list())


@sv_waves_tower.on_regex(
    r"^深塔信息(?:第)?(\d+)期?$|^深塔信息$|^深塔第(\d+)期$",
    block=True,
)
async def send_tower_challenge_info(bot: Bot, ev: Event):
    """查询深塔挑战信息"""

    period = None
    text = ev.text.strip()
    match = re.search(r'(\d+)', text)
    if match:
        try:
            period = int(match.group(1))
        except ValueError:
            pass

    im = await draw_tower_challenge_img(ev, period)
    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    else:
        await bot.send(im)


@sv_waves_slash_info.on_regex(
    r"^(?:海墟|冥海|无尽)信息(?:第)?(\d+)期?$|^(?:海墟|冥海|无尽)信息$|^(?:海墟|冥海|无尽)第(\d+)期$",
    block=True,
)
async def send_slash_challenge_info(bot: Bot, ev: Event):
    """查询海墟挑战信息"""

    period = None
    text = ev.text.strip()
    match = re.search(r'(\d+)', text)
    if match:
        try:
            period = int(match.group(1))
        except ValueError:
            pass

    im = await draw_slash_challenge_img(ev, period)
    if isinstance(im, str):
        at_sender = True if ev.group_id else False
        await bot.send(im, at_sender)
    else:
        await bot.send(im)
