import asyncio
import copy
import json
import re
import time
from pathlib import Path
from typing import List, Optional

import aiofiles
import httpx
from PIL import Image, ImageDraw

from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.image.image_tools import crop_center_img

from ..utils.api.model import SlashDetail
from ..utils.api.wwapi import (
    GET_SLASH_RANK_URL,
    SlashRank,
    SlashRankItem,
    SlashRankRes,
)
from ..utils.ascension.char import get_char_model
from ..utils.cache import TimedCache
from ..utils.database.models import WavesBind
from ..utils.fonts.waves_fonts import (
    waves_font_12,
    waves_font_16,
    waves_font_18,
    waves_font_20,
    waves_font_34,
    waves_font_44,
    waves_font_58,
)
from ..utils.image import (
    AMBER,
    RED,
    WAVES_FREEZING,
    WAVES_LINGERING,
    WAVES_MOLTEN,
    WAVES_MOONLIT,
    WAVES_SIERRA,
    WAVES_VOID,
    add_footer,
    get_ICON,
    get_qq_avatar,
    get_square_avatar,
    get_waves_bg,
    pic_download_from_url,
)
from ..utils.resource.RESOURCE_PATH import SLASH_PATH
from ..utils.util import get_version
from ..utils.waves_api import waves_api
from ..wutheringwaves_abyss.draw_slash_card import COLOR_QUALITY
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig


async def get_endless_rank_token_condition(ev):
    """检查无尽排行的权限配置"""
    # 群组 不限制token
    WavesRankNoLimitGroup = WutheringWavesConfig.get_config(
        "WavesRankNoLimitGroup"
    ).data
    if WavesRankNoLimitGroup and ev.group_id in WavesRankNoLimitGroup:
        return True

    # 群组 自定义的
    WavesRankUseTokenGroup = WutheringWavesConfig.get_config(
        "WavesRankUseTokenGroup"
    ).data
    # 全局 主人定义的
    RankUseToken = WutheringWavesConfig.get_config("RankUseToken").data
    if (
        WavesRankUseTokenGroup and ev.group_id in WavesRankUseTokenGroup
    ) or RankUseToken:
        return True

    return False


TEXT_PATH = Path(__file__).parent / "texture2d"
avatar_mask = Image.open(TEXT_PATH / "avatar_mask.png")
default_avatar_char_id = "1505"
pic_cache = TimedCache(600, 200)

BOT_COLOR = [
    WAVES_MOLTEN,
    AMBER,
    WAVES_VOID,
    WAVES_SIERRA,
    WAVES_FREEZING,
    WAVES_LINGERING,
    WAVES_MOONLIT,
]


def get_score_color(score: int):
    if score >= 30000:
        return (255, 0, 0)
    elif score >= 25000:
        return (234, 183, 4)
    elif score >= 20000:
        return (185, 106, 217)
    elif score >= 15000:
        return (22, 145, 121)
    elif score >= 10000:
        return (53, 152, 219)
    else:
        return (255, 255, 255)


async def get_rank(item: SlashRankItem) -> Optional[SlashRankRes]:
    WavesToken = WutheringWavesConfig.get_config("WavesToken").data

    if not WavesToken:
        return

    async with httpx.AsyncClient() as client:
        try:
            res = await client.post(
                GET_SLASH_RANK_URL,
                json=item.dict(),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {WavesToken}",
                },
                timeout=httpx.Timeout(10),
            )
            if res.status_code == 200:
                return SlashRankRes.model_validate(res.json())
            else:
                logger.warning(f"获取排行失败: {res.status_code} - {res.text}")
        except Exception as e:
            logger.exception(f"获取排行失败: {e}")


async def draw_all_slash_rank_card(bot: Bot, ev: Event):
    waves_id = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
    match = re.search(r"(\d+)", ev.raw_text)
    if match:
        pages = int(match.group(1))
    else:
        pages = 1
    pages = max(pages, 1)  # 最小为1
    pages = min(pages, 5)  # 最大为5
    page_num = 20
    item = SlashRankItem(
        page=pages,
        page_num=page_num,
        waves_id=waves_id or "",
        version=get_version(dynamic=True, waves_id=waves_id or "", pages=pages),
    )

    rankInfoList = await get_rank(item)
    if not rankInfoList:
        return "获取排行失败"

    if rankInfoList.message and not rankInfoList.data:
        return rankInfoList.message

    if not rankInfoList.data:
        return "获取排行失败"

    # 设置图像尺寸
    width = 1300
    item_spacing = 120
    header_height = 510
    footer_height = 50
    char_list_len = len(rankInfoList.data.rank_list)

    # 计算所需的总高度
    total_height = header_height + item_spacing * char_list_len + footer_height

    # 创建带背景的画布 - 使用bg9
    card_img = get_waves_bg(width, total_height, "bg9")

    # title
    title_bg = Image.open(TEXT_PATH / "slash.jpg")
    title_bg = title_bg.crop((0, 0, width, 500))

    # icon
    icon = get_ICON()
    icon = icon.resize((128, 128))
    title_bg.paste(icon, (60, 240), icon)

    # title
    title_text = "#无尽总排行"
    title_bg_draw = ImageDraw.Draw(title_bg)
    title_bg_draw.text((220, 290), title_text, "white", waves_font_58, "lm")

    # 遮罩
    char_mask = Image.open(TEXT_PATH / "char_mask.png").convert("RGBA")
    # 根据width扩图
    char_mask = char_mask.resize((width, char_mask.height * width // char_mask.width))
    char_mask = char_mask.crop((0, char_mask.height - 500, width, char_mask.height))
    char_mask_temp = Image.new("RGBA", char_mask.size, (0, 0, 0, 0))
    char_mask_temp.paste(title_bg, (0, 0), char_mask)

    card_img.paste(char_mask_temp, (0, 0), char_mask_temp)

    rank_list = rankInfoList.data.rank_list
    tasks = [get_avatar(rank.user_id) for rank in rank_list]
    results = await asyncio.gather(*tasks)

    # 获取角色信息
    bot_color_map = {}
    bot_color = copy.deepcopy(BOT_COLOR)

    # for rank_temp_index, rank_temp in enumerate(rank_list):

    for rank_temp_index, temp in enumerate(zip(rank_list, results)):
        rank_temp: SlashRank = temp[0]
        role_avatar: Image.Image = temp[1]
        role_bg = Image.open(TEXT_PATH / "bar1.png")
        # role_bg = Image.new("RGBA", (width, info_h), (255, 255, 255, 0))
        role_bg.paste(role_avatar, (100, 0), role_avatar)
        role_bg_draw = ImageDraw.Draw(role_bg)

        # 添加排名显示
        rank_id = rank_temp.rank
        rank_color = (54, 54, 54)
        if rank_id == 1:
            rank_color = (255, 0, 0)
        elif rank_id == 2:
            rank_color = (255, 180, 0)
        elif rank_id == 3:
            rank_color = (185, 106, 217)

        def draw_rank_id(rank_id, size=(50, 50), draw=(24, 24), dest=(40, 30)):
            info_rank = Image.new("RGBA", size, color=(255, 255, 255, 0))
            rank_draw = ImageDraw.Draw(info_rank)
            rank_draw.rounded_rectangle(
                [0, 0, size[0], size[1]], radius=8, fill=rank_color + (int(0.9 * 255),)
            )
            rank_draw.text(draw, f"{rank_id}", "white", waves_font_34, "mm")
            role_bg.alpha_composite(info_rank, dest)

        # rank_id = index + 1 + (pages - 1) * 20
        if rank_id > 999:
            draw_rank_id("999+", size=(100, 50), draw=(50, 24), dest=(10, 30))
        elif rank_id > 99:
            draw_rank_id(rank_id, size=(75, 50), draw=(37, 24), dest=(25, 30))
        else:
            draw_rank_id(rank_id, size=(50, 50), draw=(24, 24), dest=(40, 30))

        # 名字
        role_bg_draw.text(
            (210, 75), f"{rank_temp.kuro_name}", "white", waves_font_20, "lm"
        )

        # uid
        uid_color = "white"
        if rank_temp.waves_id == item.waves_id:
            uid_color = RED
        role_bg_draw.text(
            (350, 40), f"特征码: {rank_temp.waves_id}", uid_color, waves_font_20, "lm"
        )

        # bot主人名字
        botName = rank_temp.alias_name if rank_temp.alias_name else ""
        if botName:
            color = (54, 54, 54)
            if botName in bot_color_map:
                color = bot_color_map[botName]
            elif bot_color:
                color = bot_color.pop(0)
                bot_color_map[botName] = color

            info_block = Image.new("RGBA", (200, 30), color=(255, 255, 255, 0))
            info_block_draw = ImageDraw.Draw(info_block)
            info_block_draw.rounded_rectangle(
                [0, 0, 200, 30], radius=6, fill=color + (int(0.6 * 255),)
            )
            info_block_draw.text(
                (100, 15), f"bot: {botName}", "white", waves_font_18, "mm"
            )
            role_bg.alpha_composite(info_block, (350, 66))

        # 总分数
        role_bg_draw.text(
            (1140, 55),
            f"{rank_temp.score}",
            get_score_color(rank_temp.score),
            waves_font_44,
            "mm",
        )

        for half_index, slash_half in enumerate(rank_temp.half_list):

            for role_index, char_detail in enumerate(slash_half.char_detail):
                char_id = char_detail.char_id
                char_level = char_detail.level
                char_chain = char_detail.chain

                char_model = get_char_model(char_id)
                if char_model is None:
                    continue
                char_avatar = await get_square_avatar(char_id)
                char_avatar = char_avatar.resize((45, 45))

                if char_chain != -1:
                    info_block = Image.new("RGBA", (20, 20), color=(255, 255, 255, 0))
                    info_block_draw = ImageDraw.Draw(info_block)
                    info_block_draw.rectangle(
                        [0, 0, 20, 20], fill=(96, 12, 120, int(0.9 * 255))
                    )
                    info_block_draw.text(
                        (8, 8),
                        f"{char_chain}",
                        "white",
                        waves_font_12,
                        "mm",
                    )
                    char_avatar.paste(info_block, (30, 30), info_block)

                role_bg.alpha_composite(
                    char_avatar, (570 + half_index * 250 + role_index * 50, 20)
                )

            # buff
            buff_bg = Image.new("RGBA", (50, 50), (255, 255, 255, 0))
            buff_bg_draw = ImageDraw.Draw(buff_bg)
            buff_bg_draw.rounded_rectangle(
                [0, 0, 50, 50],
                radius=5,
                fill=(0, 0, 0, int(0.8 * 255)),
            )
            buff_color = COLOR_QUALITY[slash_half.buff_quality]
            buff_bg_draw.rectangle(
                [0, 45, 50, 50],
                fill=buff_color,
            )
            buff_pic = await pic_download_from_url(SLASH_PATH, slash_half.buff_icon)
            buff_pic = buff_pic.resize((50, 50))
            buff_bg.paste(buff_pic, (0, 0), buff_pic)

            role_bg.alpha_composite(buff_bg, (720 + half_index * 250, 15))

            # 分数
            role_bg_draw.text(
                (670 + half_index * 250, 80),
                f"{slash_half.score}",
                get_score_color(slash_half.score),
                waves_font_20,
                "mm",
            )

        card_img.paste(role_bg, (0, 510 + rank_temp_index * item_spacing), role_bg)

    card_img = add_footer(card_img)
    card_img = await convert_img(card_img)
    return card_img


async def get_avatar(
    qid: Optional[str],
) -> Image.Image:
    # 检查qid 为纯数字
    if qid and qid.isdigit():
        if WutheringWavesConfig.get_config("QQPicCache").data:
            pic = pic_cache.get(qid)
            if not pic:
                pic = await get_qq_avatar(qid, size=100)
                pic_cache.set(qid, pic)
        else:
            pic = await get_qq_avatar(qid, size=100)
            pic_cache.set(qid, pic)
        pic_temp = crop_center_img(pic, 120, 120)

        img = Image.new("RGBA", (180, 180))
        avatar_mask_temp = avatar_mask.copy()
        mask_pic_temp = avatar_mask_temp.resize((120, 120))
        img.paste(pic_temp, (0, -5), mask_pic_temp)
    else:
        pic = await get_square_avatar(default_avatar_char_id)

        pic_temp = Image.new("RGBA", pic.size)
        pic_temp.paste(pic.resize((160, 160)), (10, 10))
        pic_temp = pic_temp.resize((160, 160))

        avatar_mask_temp = avatar_mask.copy()
        mask_pic_temp = Image.new("RGBA", avatar_mask_temp.size)
        mask_pic_temp.paste(avatar_mask_temp, (-20, -45), avatar_mask_temp)
        mask_pic_temp = mask_pic_temp.resize((160, 160))

        img = Image.new("RGBA", (180, 180))
        img.paste(pic_temp, (0, 0), mask_pic_temp)

    return img


class SlashRankListInfo:
    """无尽排行信息"""

    def __init__(
        self, user_id: str, uid: str, slash_data: Optional[SlashDetail] = None
    ):
        self.user_id = user_id
        self.uid = uid
        self.slash_data = slash_data
        self.score = 0

        if slash_data and slash_data.difficultyList:
            # 获取难度12的分数
            difficulty_12 = next(
                (k for k in slash_data.difficultyList if k.difficulty == 2), None
            )
            if difficulty_12 and difficulty_12.challengeList:
                challenge = difficulty_12.challengeList[0]
                if challenge.halfList:
                    # 计算总分数
                    self.score = sum(half.score for half in challenge.halfList)


async def get_all_slash_rank_info(
    users: List[WavesBind],
) -> List[SlashRankListInfo]:
    """从本地获取所有用户的无尽排行信息"""
    from ..utils.resource.RESOURCE_PATH import PLAYER_PATH

    rankInfoList = []

    for user in users:
        if not user.uid:
            continue

        # 处理多个uid（用下划线连接）
        for uid in user.uid.split("_"):
            # 从本地读取该用户的无尽数据
            try:
                slash_data_path = Path(PLAYER_PATH / uid / "slashData.json")
                if not slash_data_path.exists():
                    continue

                async with aiofiles.open(slash_data_path, mode="r", encoding="utf-8") as f:
                    slash_data = json.loads(await f.read())

                if not slash_data or not slash_data.get("isUnlock", False):
                    continue

                slash_data = SlashDetail.model_validate(slash_data)

                rankInfo = SlashRankListInfo(user.user_id, uid, slash_data)
                if rankInfo.score > 0:
                    rankInfoList.append(rankInfo)
            except Exception as e:
                logger.debug(f"获取用户{uid}本地无尽数据失败: {e}")
                continue

    return rankInfoList


async def get_role_chain_count(uid: str, role_id: int) -> int:
    """从rawData.json获取角色共鸣链数量"""
    from ..utils.resource.RESOURCE_PATH import PLAYER_PATH

    try:
        raw_data_path = Path(PLAYER_PATH / str(uid) / "rawData.json")
        if not raw_data_path.exists():
            return -1

        async with aiofiles.open(raw_data_path, mode="r", encoding="utf-8") as f:
            raw_data = json.loads(await f.read())

        # rawData是一个列表，包含每个角色的详细信息
        if isinstance(raw_data, list):
            for role_data in raw_data:
                if role_data.get("role", {}).get("roleId") == role_id:
                    # 获取chainList长度
                    chain_list = role_data.get("chainList", [])
                    unlocked_chains = [c for c in chain_list if c.get("unlocked", False)]
                    return len(unlocked_chains)
        return -1
    except Exception as e:
        logger.debug(f"获取角色{role_id}共鸣链失败: {e}")
        return -1


async def get_five_star_chain_total(uid: str) -> int:
    """计算五星角色的金数（0链=1金，6链=7金，即链数+1）"""
    from ..utils.resource.RESOURCE_PATH import PLAYER_PATH

    try:
        raw_data_path = Path(PLAYER_PATH / str(uid) / "rawData.json")
        if not raw_data_path.exists():
            return 0

        async with aiofiles.open(raw_data_path, mode="r", encoding="utf-8") as f:
            raw_data = json.loads(await f.read())

        total_gold = 0
        if isinstance(raw_data, list):
            for role_data in raw_data:
                role_id = role_data.get("role", {}).get("roleId")
                if role_id:
                    char_model = get_char_model(role_id)
                    # 检查是否是五星角色
                    if char_model and char_model.starLevel == 5:
                        chain_list = role_data.get("chainList", [])
                        unlocked_chains = [c for c in chain_list if c.get("unlocked", False)]
                        # 金数 = 共鸣链数 + 1
                        total_gold += len(unlocked_chains) + 1
        return total_gold
    except Exception as e:
        logger.debug(f"计算五星角色金数失败: {e}")
        return 0


async def draw_slash_rank_list(bot: Bot, ev: Event):
    """绘制无尽排行"""
    start_time = time.time()
    logger.info(f"[draw_slash_rank_list] start: {start_time}")

    # 检查权限配置
    tokenLimitFlag = await get_endless_rank_token_condition(ev)

    # 获取群里的所有用户
    users = await WavesBind.get_group_all_uid(ev.group_id)
    if not users:
        msg = []
        msg.append(f"[鸣潮] 群【{ev.group_id}】暂无无尽排行数据")
        msg.append(f"请使用【{PREFIX}无尽】后再使用此功能！")
        if tokenLimitFlag:
            msg.append(
                f"当前排行开启了登录验证，请使用命令【{PREFIX}登录】登录后此功能！"
            )
        msg.append("")
        return "\n".join(msg)

    rankInfoList = await get_all_slash_rank_info(list(users))
    if len(rankInfoList) == 0:
        msg = []
        msg.append(f"[鸣潮] 群【{ev.group_id}】暂无无尽排行数据")
        msg.append(f"请使用【{PREFIX}无尽】后再使用此功能！")
        if tokenLimitFlag:
            msg.append(
                f"当前排行开启了登录验证，请使用命令【{PREFIX}登录】登录后此功能！"
            )
        msg.append("")
        return "\n".join(msg)

    # 按分数排序
    rankInfoList.sort(key=lambda i: i.score, reverse=True)

    # 获取自己的排名
    self_uid = None
    rankId = None
    rankInfo = None
    try:
        self_uid = await WavesBind.get_uid_by_game(ev.user_id, ev.bot_id)
        if self_uid:
            rankId, rankInfo = next(
                (
                    (rankId, rankInfo)
                    for rankId, rankInfo in enumerate(rankInfoList, start=1)
                    if rankInfo.uid == self_uid and ev.user_id == rankInfo.user_id
                ),
                (None, None),
            )
    except Exception as _:
        pass

    rank_length = 20  # 显示前20条
    rankInfoList_display = rankInfoList[:rank_length]
    if rankId and rankInfo and rankId > rank_length:
        rankInfoList_display.append(rankInfo)

    # 设置图像尺寸
    width = 1000
    item_spacing = 120
    header_height = 510
    footer_height = 50

    # 计算所需的总高度
    total_height = header_height + item_spacing * len(rankInfoList_display) + footer_height

    # 创建带背景的画布
    card_img = get_waves_bg(width, total_height, "bg9")

    # title
    title_bg = Image.open(TEXT_PATH / "slash.jpg")
    title_bg = title_bg.crop((0, 0, width, 475))

    # icon
    icon = get_ICON()
    icon = icon.resize((128, 128))
    title_bg.paste(icon, (60, 240), icon)

    # title
    title_text = "#无尽群排行"
    title_bg_draw = ImageDraw.Draw(title_bg)
    title_bg_draw.text((220, 290), title_text, "white", waves_font_58, "lm")

    # 遮罩
    char_mask = Image.open(TEXT_PATH / "char_mask.png").convert("RGBA")
    # 根据width扩图
    char_mask = char_mask.resize((width, char_mask.height * width // char_mask.width))
    char_mask = char_mask.crop((0, char_mask.height - 475, width, char_mask.height))
    char_mask_temp = Image.new("RGBA", char_mask.size, (0, 0, 0, 0))
    char_mask_temp.paste(title_bg, (0, 0), char_mask)

    card_img.paste(char_mask_temp, (0, 0), char_mask_temp)

    # 获取头像
    tasks = [get_avatar(rank.user_id) for rank in rankInfoList_display]
    results = await asyncio.gather(*tasks)

    # 绘制排行条目
    bar = Image.open(TEXT_PATH / "bar2.png")

    for rank_temp_index, temp in enumerate(zip(rankInfoList_display, results)):
        rankInfo = temp[0]
        role_avatar = temp[1]
        role_bg = bar.copy()
        role_bg.paste(role_avatar, (100, 0), role_avatar)
        role_bg_draw = ImageDraw.Draw(role_bg)

        # 排名
        rank_id = rank_temp_index + 1
        rank_color = (54, 54, 54)
        if rank_id == 1:
            rank_color = (255, 0, 0)
        elif rank_id == 2:
            rank_color = (255, 180, 0)
        elif rank_id == 3:
            rank_color = (185, 106, 217)

        def draw_rank_id(rank_id, size=(50, 50), draw=(24, 24), dest=(40, 30)):
            info_rank = Image.new("RGBA", size, color=(255, 255, 255, 0))
            rank_draw = ImageDraw.Draw(info_rank)
            rank_draw.rounded_rectangle(
                [0, 0, size[0], size[1]], radius=8, fill=rank_color + (int(0.9 * 255),)
            )
            rank_draw.text(draw, f"{rank_id}", "white", waves_font_34, "mm")
            role_bg.alpha_composite(info_rank, dest)

        if rank_id > 999:
            draw_rank_id("999+", size=(100, 50), draw=(50, 24), dest=(10, 30))
        elif rank_id > 99:
            draw_rank_id(rank_id, size=(75, 50), draw=(37, 24), dest=(25, 30))
        else:
            draw_rank_id(rank_id, size=(50, 50), draw=(24, 24), dest=(40, 30))

        # 计算出场角色的金数
        char_gold_total = 0
        if rankInfo.slash_data and rankInfo.slash_data.difficultyList:
            difficulty_12 = next(
                (k for k in rankInfo.slash_data.difficultyList if k.difficulty == 2), None
            )
            if difficulty_12 and difficulty_12.challengeList:
                challenge = difficulty_12.challengeList[0]
                if challenge.halfList:
                    for slash_half in challenge.halfList:
                        for slash_role in slash_half.roleList:
                            chain_count = await get_role_chain_count(rankInfo.uid, slash_role.roleId)
                            char_gold_total += (chain_count + 1) if chain_count >= 0 else 0
       
        role_bg_draw.text(
            (210, 40), f"角色金数: {char_gold_total}", "white", waves_font_18, "lm"
        )

        # 特征码（白色UID）
        uid_color = "white"
        if rankInfo.uid == self_uid:
            uid_color = RED
        role_bg_draw.text(
            (210, 70), f"{rankInfo.uid}", uid_color, waves_font_20, "lm"
        )

        # 总分数
        role_bg_draw.text(
            (880, 55),
            f"{rankInfo.score}",
            get_score_color(rankInfo.score),
            waves_font_44,
            "mm",
        )

        # 绘制角色和信物信息
        if rankInfo.slash_data and rankInfo.slash_data.difficultyList:
            # 获取难度12的数据
            difficulty_12 = next(
                (k for k in rankInfo.slash_data.difficultyList if k.difficulty == 2), None
            )
            if difficulty_12 and difficulty_12.challengeList:
                challenge = difficulty_12.challengeList[0]
                if challenge.halfList:
                    for half_index, slash_half in enumerate(challenge.halfList):
                        # 绘制角色信息
                        for role_index, slash_role in enumerate(slash_half.roleList):
                            try:
                                char_avatar = await get_square_avatar(slash_role.roleId)
                                char_avatar = char_avatar.resize((45, 45))

                                # 获取角色共鸣链
                                chain_count = await get_role_chain_count(rankInfo.uid, slash_role.roleId)
                                if chain_count != -1:
                                    info_block = Image.new("RGBA", (20, 20), color=(255, 255, 255, 0))
                                    info_block_draw = ImageDraw.Draw(info_block)
                                    info_block_draw.rectangle(
                                        [0, 0, 20, 20], fill=(96, 12, 120, int(0.9 * 255))
                                    )
                                    info_block_draw.text(
                                        (8, 8),
                                        f"{chain_count}",
                                        "white",
                                        waves_font_12,
                                        "mm",
                                    )
                                    char_avatar.paste(info_block, (30, 30), info_block)

                                role_bg.alpha_composite(
                                    char_avatar,
                                    (350 + half_index * 235 + role_index * 50, 20),
                                )
                            except Exception as e:
                                logger.debug(f"绘制角色{slash_role.roleId}失败: {e}")

                        # 绘制信物
                        try:
                            buff_bg = Image.new("RGBA", (50, 50), (255, 255, 255, 0))
                            buff_bg_draw = ImageDraw.Draw(buff_bg)
                            buff_bg_draw.rounded_rectangle(
                                [0, 0, 50, 50],
                                radius=5,
                                fill=(0, 0, 0, int(0.8 * 255)),
                            )
                            buff_color = COLOR_QUALITY[slash_half.buffQuality]
                            buff_bg_draw.rectangle(
                                [0, 45, 50, 50],
                                fill=buff_color,
                            )
                            buff_pic = await pic_download_from_url(SLASH_PATH, slash_half.buffIcon)
                            buff_pic = buff_pic.resize((50, 50))
                            buff_bg.paste(buff_pic, (0, 0), buff_pic)
                            role_bg.alpha_composite(buff_bg, (500 + half_index * 235, 15))
                        except Exception as e:
                            logger.debug(f"绘制信物失败: {e}")

                        # 显示半分数（在信物和角色下方）
                        role_bg_draw.text(
                            (450 + half_index * 230, 80),
                            f"{slash_half.score}",
                            get_score_color(slash_half.score),
                            waves_font_20,
                            "mm",
                        )

        card_img.paste(role_bg, (0, 510 + rank_temp_index * item_spacing), role_bg)

    card_img = add_footer(card_img)
    card_img = await convert_img(card_img)

    logger.info(f"[draw_slash_rank_list] end: {time.time() - start_time}")
    return card_img
