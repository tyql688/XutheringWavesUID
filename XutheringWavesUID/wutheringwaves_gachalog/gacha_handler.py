import time
import random
import string
import traceback
from datetime import datetime, timedelta

import aiohttp
from aiohttp import TCPConnector

from gsuid_core.logger import logger

# Mappings
POOL_TYPE_MAP = {
    "角色精准调谐": "1",
    "武器精准调谐": "2",
    "角色调谐（常驻池）": "3",
    "武器调谐（常驻池）": "4",
    "新手调谐": "5",
    "新手自选唤取": "6",
    "新手自选唤取（感恩定向唤取）": "7",
    "角色新旅唤取": "8",
    "武器新旅唤取": "9",
}

FILLER_ITEM = {"resourceId": 21040023, "qualityLevel": 3, "resourceType": "武器", "name": "源能臂铠·测肆", "count": 1}


def _time_to_timestamp(time_str: str) -> float:
    if not time_str:
        return float("-inf")
    try:
        return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return float("-inf")


def _sort_key_by_time(item: dict, idx_field: str = "_internal_idx"):
    ts = _time_to_timestamp(item.get("time", ""))
    order_idx = item.get(idx_field, float("inf"))
    return (-ts, order_idx)


def generate_random_string(length, chars):
    return "".join(random.choice(chars) for _ in range(length))


def generate_union_id(length=28):
    chars = string.ascii_letters + string.digits + "_"
    return generate_random_string(length, chars)


def generate_sign(length=32):
    chars = string.digits + "abcdef"
    return generate_random_string(length, chars)


def get_timestamp_minus_1s(time_str):
    try:
        dt = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
        dt_new = dt - timedelta(seconds=1)
        return dt_new.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return time_str


async def fetch_mcgf_data(uid: str):
    logger.debug(f"[GachaHandler] 开始获取工坊数据 UID: {uid}")
    url = "https://api3.sanyueqi.cn/api/v2/game_user/get_sr_draw_v3"
    current_time_ms = str(int(time.time() * 1000))
    random_union_id = generate_union_id()
    random_sign = generate_sign()

    params = {"uid": uid, "union_id": random_union_id}

    headers = {
        "Host": "api3.sanyueqi.cn",
        "Connection": "keep-alive",
        "time": current_time_ms,
        "sign": random_sign,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF WindowsWechat(0x63090a13) UnifiedPCWindowsWechat(0xf2541411) XWEB/16965",
        "xweb_xhr": "1",
        "Content-Type": "application/json",
        "version": "100",
        "platform": "weixin",
        "Accept": "*/*",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Referer": "https://servicewechat.com/wx715e22143bcda767/36/page-frame.html",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "WWUIDMSG": "We welcome data sharing. We can also provide method to import wwuid gacha data into your mini program.",
    }

    try:
        async with aiohttp.ClientSession(connector=TCPConnector(ssl=False)) as session:
            async with session.get(url, params=params, headers=headers, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data", {}).get("uid"):
                        logger.success(f"[GachaHandler] 获取工坊数据成功 UID: {uid}")
                        return data
                    else:
                        logger.warning(f"[GachaHandler] 获取工坊数据失败 UID: {uid} 返回数据异常：{str(data)[:500]}")
                else:
                    logger.warning(f"[GachaHandler] 获取工坊数据失败 Status: {response.status}")
    except Exception as e:
        logger.error(f"[GachaHandler] 获取工坊数据发生异常: {e}")
        logger.error(traceback.format_exc())
    return None


def merge_gacha_data(original_data: dict, latest_data: dict) -> dict:
    logger.debug("[GachaHandler] 开始合并抽卡记录...")

    export_info = original_data.get("info", {})
    if not export_info:
        uid = latest_data.get("data", {}).get("uid")
        if uid:
            now = datetime.now()
            export_info = {
                "export_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                "export_app": "WutheringWavesUID",
                "export_app_version": "v2.0",
                "export_timestamp": int(now.timestamp()),
                "version": "v2.0",
                "uid": str(uid),
            }
            logger.debug(f"[GachaHandler] 本地记录为空，已重建 info 信息 (UID: {uid})")
        else:
            logger.warning("[GachaHandler] 无法获取 UID，info 信息可能不完整")

    original_list = original_data.get("list", [])

    for idx, item in enumerate(original_list):
        item["_internal_idx"] = idx

    latest_5stars = []
    card_analysis = latest_data.get("data", {}).get("card_analysis_json", {})

    def extract_five_cards(d):
        if isinstance(d, dict):
            if "five_cards" in d and isinstance(d["five_cards"], list):
                for card in d["five_cards"]:
                    p_type = card.get("cardPoolType")
                    p_type_code = POOL_TYPE_MAP.get(p_type, p_type)

                    card_name = card.get("name", "未知五星")
                    card_time = card.get("time", "")
                    draw_total = card.get("draw_total", 1)

                    if not card_time:
                        continue

                    latest_5stars.append(
                        {
                            "time": card_time,
                            "name": card_name,
                            "cardPoolType": p_type_code,
                            "draw_total": draw_total,
                            "resourceId": card.get("resourceId", card.get("item_id")),
                            "qualityLevel": 5,
                            "resourceType": card.get("resourceType", "角色"),
                            "is_latest": True,
                        }
                    )
            for k, v in d.items():
                extract_five_cards(v)
        elif isinstance(d, list):
            for item in d:
                extract_five_cards(item)

    extract_five_cards(card_analysis)
    logger.debug(f"[GachaHandler] 解析出最新五星记录 {len(latest_5stars)} 条")

    orig_types = [str(x.get("cardPoolType")) for x in original_list if x.get("cardPoolType")]
    latest_types = [str(x.get("cardPoolType")) for x in latest_5stars if x.get("cardPoolType")]

    all_pools = set(orig_types + latest_types)

    merged_list = []

    for pool_id in sorted(list(all_pools)):
        O_all = sorted(
            [x for x in original_list if str(x.get("cardPoolType")) == str(pool_id)],
            key=_sort_key_by_time,
        )
        O_all.reverse()
        L_5s = sorted(
            [x for x in latest_5stars if str(x.get("cardPoolType")) == str(pool_id)],
            key=_sort_key_by_time,
        )
        L_5s.reverse()

        O_5s = [x for x in O_all if x.get("qualityLevel") == 5]

        if O_5s:
            newest_local_time = _time_to_timestamp(O_5s[-1]["time"])
            L_5s_filtered = [x for x in L_5s if _time_to_timestamp(x["time"]) < newest_local_time]
            logger.debug(
                f"[GachaHandler] Pool {pool_id}: 本地最新五星时间 {O_5s[-1]['time']}, "
                f"过滤后保留 {len(L_5s_filtered)}/{len(L_5s)} 条工坊记录"
            )
            L_5s = L_5s_filtered

        pool_merged_items = []

        if not O_5s:
            logger.debug(f"[GachaHandler] Pool {pool_id}: 无本地五星记录，重建所有历史")
            for cp in L_5s:
                filler_count = cp["draw_total"] - 1
                filler_time = get_timestamp_minus_1s(cp["time"])
                for _ in range(filler_count):
                    f = FILLER_ITEM.copy()
                    f["cardPoolType"] = str(pool_id)
                    f["time"] = filler_time
                    pool_merged_items.append(f)
                cp_item = {
                    "cardPoolType": str(pool_id),
                    "resourceId": cp["resourceId"],
                    "qualityLevel": 5,
                    "resourceType": cp["resourceType"],
                    "name": cp["name"],
                    "count": 1,
                    "time": cp["time"],
                }
                pool_merged_items.append(cp_item)
            pool_merged_items.extend(O_all)

        else:
            x = O_5s[0]
            logger.debug(f"[GachaHandler] Pool {pool_id}: 最早本地五星为 {x.get('name')} ({x.get('time')})")

            match_idx = None
            for i, cand in enumerate(L_5s):
                if cand["time"] == x["time"] and cand["name"] == x["name"]:
                    is_match = True
                    for offset in range(1, 3):
                        if (i + offset < len(L_5s)) and (offset < len(O_5s)):
                            l_next = L_5s[i + offset]
                            o_next = O_5s[offset]
                            if l_next["time"] != o_next["time"] or l_next["name"] != o_next["name"]:
                                is_match = False
                                break
                    if is_match:
                        match_idx = i
                        break

            if match_idx is None:
                logger.warning(f"[GachaHandler] Pool {pool_id}: 未找到五星匹配点，执行分离合并")
                for cp in L_5s:
                    filler_count = cp["draw_total"] - 1
                    filler_time = get_timestamp_minus_1s(cp["time"])
                    for _ in range(filler_count):
                        f = FILLER_ITEM.copy()
                        f["cardPoolType"] = str(pool_id)
                        f["time"] = filler_time
                        pool_merged_items.append(f)
                    cp_item = {
                        "cardPoolType": str(pool_id),
                        "resourceId": cp["resourceId"],
                        "qualityLevel": 5,
                        "resourceType": cp["resourceType"],
                        "name": cp["name"],
                        "count": 1,
                        "time": cp["time"],
                    }
                    pool_merged_items.append(cp_item)
                pool_merged_items.extend(O_all)

            else:
                logger.debug(f"[GachaHandler] Pool {pool_id}: 在索引 {match_idx} 处对其，重建之前历史")
                for i in range(match_idx):
                    cp = L_5s[i]
                    filler_count = cp["draw_total"] - 1
                    filler_time = get_timestamp_minus_1s(cp["time"])
                    for _ in range(filler_count):
                        f = FILLER_ITEM.copy()
                        f["cardPoolType"] = str(pool_id)
                        f["time"] = filler_time
                        pool_merged_items.append(f)
                    cp_item = {
                        "cardPoolType": str(pool_id),
                        "resourceId": cp["resourceId"],
                        "qualityLevel": 5,
                        "resourceType": cp["resourceType"],
                        "name": cp["name"],
                        "count": 1,
                        "time": cp["time"],
                    }
                    pool_merged_items.append(cp_item)

                cp_x = L_5s[match_idx]

                items_before_x = []
                target_internal_idx = x.get("_internal_idx", -1)

                for item in O_all:
                    if item.get("_internal_idx", -2) == target_internal_idx:
                        break
                    items_before_x.append(item)

                count_existing = len(items_before_x)
                target_count = cp_x["draw_total"] - 1

                diff = target_count - count_existing
                logger.debug(
                    f"[GachaHandler] Pool {pool_id}: 连接点需填充 {diff} (目标 {target_count} - 现有 {count_existing})"
                )

                if diff > 0:
                    filler_time = get_timestamp_minus_1s(x["time"])
                    fillers = []
                    for _ in range(diff):
                        f = FILLER_ITEM.copy()
                        f["cardPoolType"] = str(pool_id)
                        f["time"] = filler_time
                        fillers.append(f)
                    pool_merged_items.extend(fillers)

                pool_merged_items.extend(O_all)

        merged_list.extend(pool_merged_items)

    merged_list.sort(key=_sort_key_by_time)
    for item in merged_list:
        if "_internal_idx" in item:
            del item["_internal_idx"]
    logger.success(f"[GachaHandler] 合并完成，共 {len(merged_list)} 条记录")

    return {"info": export_info, "list": merged_list}
