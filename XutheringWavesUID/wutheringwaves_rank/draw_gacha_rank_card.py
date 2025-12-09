import asyncio
from typing import List, Union
from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.logger import logger
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from .slash_rank import get_avatar
from ..utils.image import (
    RED,
    SPECIAL_GOLD,
    get_ICON,
    add_footer,
    get_waves_bg,
)
from ..utils.database.models import WavesBind
from ..wutheringwaves_config import PREFIX, WutheringWavesConfig
from ..utils.fonts.waves_fonts import (
    waves_font_18,
    waves_font_20,
    waves_font_28,
    waves_font_34,
    waves_font_58,
)
from ..wutheringwaves_gachalog.draw_gachalogs import get_gacha_stats

TEXT_PATH = Path(__file__).parent / "texture2d"
avatar_mask = Image.open(TEXT_PATH / "avatar_mask.png")
pic_cache = None


class GachaRankCard:
    """抽卡排行卡片信息"""

    def __init__(self, user_id: str, uid: str, stats: dict):
        self.user_id = user_id
        self.uid = uid
        self.stats = stats
        # 获取角色和武器的抽数
        char_pool = stats.get("角色精准调谐", {})
        weapon_pool = stats.get("武器精准调谐", {})

        # 平均抽数
        self.char_avg = char_pool.get("avg_up", 0) or char_pool.get("avg", 0)
        self.weapon_avg = weapon_pool.get("avg_up", 0) or weapon_pool.get("avg", 0)

        # 总抽数
        self.total_count = char_pool.get("total", 0) + weapon_pool.get("total", 0)

        # 获取角色金数和武器金数（直接从 gachaStats 中读取，不加权）
        self.char_gold = char_pool.get("char_gold", 0)
        self.weapon_gold = weapon_pool.get("weapon_gold", 0)
        self.gold_total = self.char_gold + self.weapon_gold

        # 计算加权抽数：使用实际投入加权公式
        denominator = 81 * self.char_gold + 54 * self.weapon_gold
        if denominator > 0:
            self.weighted = (self.char_avg * self.char_gold + self.weapon_avg * self.weapon_gold) / denominator * 100
        else:
            self.weighted = 1000


async def get_all_gacha_rank_info(users: List[WavesBind], bot_id: str) -> List[GachaRankCard]:
    """获取所有用户的抽卡排行信息"""
    rankInfoList = []

    for user in users:
        if not user.user_id:
            continue

        # 处理多个uid（用下划线连接）
        if not user.uid:
            continue

        for uid in user.uid.split("_"):
            try:
                stats = await get_gacha_stats(uid)
                if not stats:
                    continue

                rankInfo = GachaRankCard(user.user_id, uid, stats)

                # 获取配置的最小抽数阈值
                min_pull = WutheringWavesConfig.get_config("GachaRankMin").data
                if rankInfo.total_count < min_pull:
                    continue

                rankInfoList.append(rankInfo)
            except Exception as e:
                logger.debug(f"获取用户{uid}抽卡排行数据失败: {e}")
                continue

    return rankInfoList


async def get_gacha_rank_token_condition(ev):
    """检查抽卡排行的权限配置"""
    # 群组 不限制token
    WavesRankNoLimitGroup = WutheringWavesConfig.get_config("WavesRankNoLimitGroup").data
    if WavesRankNoLimitGroup and ev.group_id in WavesRankNoLimitGroup:
        return True

    # 群组 自定义的
    WavesRankUseTokenGroup = WutheringWavesConfig.get_config("WavesRankUseTokenGroup").data
    # 全局 主人定义的
    RankUseToken = WutheringWavesConfig.get_config("RankUseToken").data
    if (WavesRankUseTokenGroup and ev.group_id in WavesRankUseTokenGroup) or RankUseToken:
        return True

    return False


async def draw_gacha_rank_card(bot, ev: Event) -> Union[str, bytes]:
    """绘制抽卡排行"""
    # 检查权限配置
    tokenLimitFlag = await get_gacha_rank_token_condition(ev)

    # 获取配置的最小抽数阈值
    min_pull = WutheringWavesConfig.get_config("GachaRankMin").data

    # 解析参数以获取排序类型
    text = ev.text.strip() if ev.text else ""
    sort_reverse = False
    if text:
        if "非" in text:
            sort_reverse = True
        elif "欧" in text:
            sort_reverse = False

    # 获取群里的所有用户
    users = await WavesBind.get_group_all_uid(ev.group_id)
    if not users:
        msg = []
        msg.append(f"[鸣潮] 群【{ev.group_id}】暂无抽卡排行数据")
        msg.append(f"请使用【{PREFIX}导入抽卡记录】后再使用此功能！")
        if tokenLimitFlag:
            msg.append(f"当前排行开启了登录验证，请使用命令【{PREFIX}登录】登录后此功能！")
        return "\n".join(msg)

    rankInfoList = await get_all_gacha_rank_info(list(users), ev.bot_id)
    if len(rankInfoList) == 0:
        msg = []
        msg.append(f"[鸣潮] 群【{ev.group_id}】暂无抽卡排行数据")
        msg.append(f"请使用【{PREFIX}导入抽卡记录】后再使用此功能！")
        if tokenLimitFlag:
            msg.append(f"当前排行开启了登录验证，请使用命令【{PREFIX}登录】登录后此功能！")
        return "\n".join(msg)

    # 按加权抽数排序（分数越低越欧，反向排序则是非）
    rankInfoList.sort(key=lambda i: i.weighted, reverse=sort_reverse)
    rankInfoList_with_id = list(enumerate(rankInfoList, start=1))

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
                    for rankId, rankInfo in rankInfoList_with_id
                    if rankInfo.uid == self_uid and ev.user_id == rankInfo.user_id
                ),
                (None, None),
            )
    except Exception:
        pass

    rank_length = 20  # 显示前20条
    rankInfoList_display = rankInfoList_with_id[:rank_length]
    if rankId and rankInfo and rankId > rank_length:
        rankInfoList_display.append((rankId, rankInfo))

    width = 1000
    text_bar_height = 130
    item_spacing = 120
    header_height = 510
    footer_height = 50

    # 计算所需的总高度
    total_height = header_height + text_bar_height + item_spacing * len(rankInfoList_display) + footer_height

    # 创建带背景的画布
    card_img = get_waves_bg(width, total_height, "bg9")

    # 排行说明栏
    text_bar_img = Image.new("RGBA", (width, 130), color=(0, 0, 0, 0))
    text_bar_draw = ImageDraw.Draw(text_bar_img)
    # 绘制深灰色背景
    bar_bg_color = (36, 36, 41, 230)
    text_bar_draw.rounded_rectangle([20, 20, width - 40, 110], radius=8, fill=bar_bg_color)

    # 绘制顶部的金色高亮线
    accent_color = (203, 161, 95)
    text_bar_draw.rectangle([20, 20, width - 40, 26], fill=accent_color)

    # 左侧标题
    text_bar_draw.text((40, 60), "排行说明", (150, 150, 150), waves_font_28, "lm")
    text_bar_draw.text(
        (185, 50),
        f"1. 仅显示总抽数≥{min_pull}的玩家",
        SPECIAL_GOLD,
        waves_font_20,
        "lm",
    )
    text_bar_draw.text(
        (185, 85), "2. UP/武器为平均抽数。加权 = 实际抽数 / (角色数×81 + 武器数×54)", SPECIAL_GOLD, waves_font_20, "lm"
    )

    card_img.alpha_composite(text_bar_img, (0, header_height))

    # title
    title_bg = Image.open(TEXT_PATH / "totalrank.jpg")
    title_bg = title_bg.crop((0, 0, width, 475))

    # icon
    icon = get_ICON()
    icon = icon.resize((128, 128))
    title_bg.paste(icon, (60, 240), icon)

    # title 文字
    title_text = "#抽卡群排行"
    title_bg_draw = ImageDraw.Draw(title_bg)
    title_bg_draw.text((220, 290), title_text, "white", waves_font_58, "lm")

    # 遮罩
    char_mask = Image.open(TEXT_PATH / "char_mask.png").convert("RGBA")
    char_mask = char_mask.resize((width, char_mask.height * width // char_mask.width))
    char_mask = char_mask.crop((0, char_mask.height - 475, width, char_mask.height))
    char_mask_temp = Image.new("RGBA", char_mask.size, (0, 0, 0, 0))
    char_mask_temp.paste(title_bg, (0, 0), char_mask)

    card_img.paste(char_mask_temp, (0, 0), char_mask_temp)

    # 获取头像
    tasks = [get_avatar(rank_info.user_id) for _, rank_info in rankInfoList_display]
    results = await asyncio.gather(*tasks)

    # 导入必要的图片资源 - 使用bar2.png，不对其进行resize
    bar = Image.open(TEXT_PATH / "bar2.png")

    # 绘制排行条目
    for rank_temp_index, temp in enumerate(zip(rankInfoList_display, results)):
        rank_id, rankInfo = temp[0]
        role_avatar = temp[1]
        y_pos = header_height + 130 + rank_temp_index * item_spacing

        # 创建条目背景 - 不对bar进行resize，使用原始尺寸
        role_bg = bar.copy()
        role_bg.paste(role_avatar, (100, 0), role_avatar)
        role_bg_draw = ImageDraw.Draw(role_bg)

        # 排名
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
            rank_draw.rounded_rectangle([0, 0, size[0], size[1]], radius=8, fill=rank_color + (int(0.9 * 255),))
            rank_draw.text(draw, f"{rank_id}", "white", waves_font_34, "mm")
            role_bg.alpha_composite(info_rank, dest)

        if rank_id > 999:
            draw_rank_id("999+", size=(100, 50), draw=(50, 24), dest=(10, 30))
        elif rank_id > 99:
            draw_rank_id(rank_id, size=(75, 50), draw=(37, 24), dest=(25, 30))
        else:
            draw_rank_id(rank_id, size=(50, 50), draw=(24, 24), dest=(40, 30))

        # 角色金数
        role_bg_draw.text(
            (210, 40), f"角色{rankInfo.char_gold}金 武器{rankInfo.weapon_gold}金", "white", waves_font_18, "lm"
        )

        # UID
        uid_color = "white"
        if rankInfo.uid == self_uid:
            uid_color = RED
        role_bg_draw.text((210, 70), f"{rankInfo.uid}", uid_color, waves_font_20, "lm")

        # UP平均抽数
        role_bg_draw.text((460, 30), "UP", SPECIAL_GOLD, waves_font_20, "mm")
        role_bg_draw.text((460, 70), f"{rankInfo.char_avg:.1f}", "white", waves_font_28, "mm")

        # 武器平均抽数
        role_bg_draw.text((600, 30), "武器", SPECIAL_GOLD, waves_font_20, "mm")
        role_bg_draw.text((600, 70), f"{rankInfo.weapon_avg:.1f}", "white", waves_font_28, "mm")

        # 加权抽数
        role_bg_draw.text((740, 30), "加权", SPECIAL_GOLD, waves_font_20, "mm")
        role_bg_draw.text((740, 70), f"{rankInfo.weighted:.1f}", "lightgreen", waves_font_28, "mm")

        # 总抽数
        role_bg_draw.text((880, 30), "总抽数", SPECIAL_GOLD, waves_font_20, "mm")
        role_bg_draw.text((880, 70), f"{rankInfo.total_count}", "white", waves_font_28, "mm")

        # 贴到背景
        card_img.paste(role_bg, (0, y_pos), role_bg)

    card_img = add_footer(card_img)
    card_img = await convert_img(card_img)
    return card_img
