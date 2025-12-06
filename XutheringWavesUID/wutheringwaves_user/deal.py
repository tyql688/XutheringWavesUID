from typing import List, Optional, Union

from gsuid_core.bot import Bot
from gsuid_core.models import Event

from ..utils.api.api import PGR_GAME_ID, WAVES_GAME_ID
from ..utils.api.model import KuroWavesUserInfo
from ..utils.api.request_util import PLATFORM_SOURCE
from ..utils.database.models import WavesBind, WavesUser
from ..utils.error_reply import ERROR_CODE, WAVES_CODE_103
from ..utils.waves_api import waves_api


async def _fetch_roles_by_game(ck: str, did: str, game_id: int):
    roles = await waves_api.get_kuro_role_list(ck, did, game_id=game_id)
    if (
        not roles.success
        or not roles.data
        or not isinstance(roles.data, list)
    ):
        return None, roles.throw_msg()
    return roles.data, None


async def add_cookie(ev: Event, ck: str, did: str) -> str:
    platform = PLATFORM_SOURCE

    waves_roles, err = await _fetch_roles_by_game(ck, did, WAVES_GAME_ID)
    pgr_roles, pgr_err = await _fetch_roles_by_game(ck, did, PGR_GAME_ID)
    if err and pgr_err:
        # 若两个游戏都失败，直接返回 waves 的错误
        return err

    role_list = []
    pgr_list = []

    if waves_roles:
        for kuroWavesUserInfo in waves_roles:
            data = KuroWavesUserInfo.model_validate(kuroWavesUserInfo)
            if data.gameId != WAVES_GAME_ID:
                continue

            user = await WavesUser.get_user_by_attr(
                ev.user_id, ev.bot_id, "uid", data.roleId
            )

            succ, bat = await waves_api.get_request_token(
                data.roleId,
                ck,
                did,
                data.serverId,
            )
            if not succ or not bat:
                return bat

            if user:
                await WavesUser.update_data_by_data(
                    select_data={
                        "user_id": ev.user_id,
                        "bot_id": ev.bot_id,
                        "uid": data.roleId,
                    },
                    update_data={
                        "cookie": ck,
                        "status": "",
                        "platform": platform,
                        "pgr_uid": user.pgr_uid,
                    },
                )
            else:
                await WavesUser.insert_data(
                    ev.user_id,
                    ev.bot_id,
                    cookie=ck,
                    uid=data.roleId,
                    platform=platform,
                    pgr_uid=None,
                )

            # 更新bat
            await WavesUser.update_data_by_data(
                select_data={
                    "user_id": ev.user_id,
                    "bot_id": ev.bot_id,
                    "uid": data.roleId,
                },
                update_data={"bat": bat, "did": did},
            )

            res = await WavesBind.insert_waves_uid(
                ev.user_id, ev.bot_id, data.roleId, ev.group_id, lenth_limit=9
            )
            if res == 0 or res == -2:
                await WavesBind.switch_uid_by_game(ev.user_id, ev.bot_id, data.roleId)

            role_list.append(
                {
                    "名字": data.roleName,
                    "特征码": data.roleId,
                }
            )

    if pgr_roles:
        for pgr_role in pgr_roles:
            data = KuroWavesUserInfo.model_validate(pgr_role)
            if data.gameId != PGR_GAME_ID:
                continue
            pgr_user = await WavesUser.get_user_by_attr(
                ev.user_id, ev.bot_id, "pgr_uid", data.roleId
            )
            if pgr_user:
                await WavesUser.update_data_by_data(
                    select_data={
                        "user_id": ev.user_id,
                        "bot_id": ev.bot_id,
                        "pgr_uid": data.roleId,
                    },
                    update_data={
                        "cookie": ck,
                        "status": "",
                        "platform": platform,
                        "pgr_uid": data.roleId,
                        "did": did,
                    },
                )
            else:
                await WavesUser.insert_data(
                    ev.user_id,
                    ev.bot_id,
                    cookie=ck,
                    uid=data.roleId,
                    pgr_uid=data.roleId,
                    platform=platform,
                    did=did,
                )

            res = await WavesBind.insert_uid(
                ev.user_id,
                ev.bot_id,
                data.roleId,
                ev.group_id,
                lenth_limit=None,
                game_name="pgr",
            )
            if res == 0 or res == -2:
                await WavesBind.switch_uid_by_game(
                    ev.user_id, ev.bot_id, data.roleId, game_name="pgr"
                )
            pgr_list.append({"名字": data.roleName, "特征码": data.roleId})

    if len(role_list) == 0 and len(pgr_list) == 0:
        return "登录失败\n"

    msg = []
    for role in role_list:
        msg.append(f"[鸣潮]【{role['名字']}】特征码【{role['特征码']}】登录成功!")
    for role in pgr_list:
        msg.append(f"[战双]【{role['名字']}】UID【{role['特征码']}】记录成功!")
    return "\n".join(msg)


async def refresh_bind(ev: Event) -> str:
    user_list = await WavesUser.select_data_list(user_id=ev.user_id, bot_id=ev.bot_id)
    if not user_list:
        return "未找到可用的token，请先登录或添加token\n"

    waves_msg: List[str] = []
    pgr_msg: List[str] = []
    invalid = False
    for user in user_list:
        if not user.cookie or user.status == "无效":
            continue

        login_res = await waves_api.login_log(user.uid, user.cookie)
        if not login_res.success:
            invalid = True
            continue

        waves_roles, err = await _fetch_roles_by_game(user.cookie, user.did, WAVES_GAME_ID)
        pgr_roles, pgr_err = await _fetch_roles_by_game(user.cookie, user.did, PGR_GAME_ID)
        if err and pgr_err:
            continue

        if waves_roles:
            for role in waves_roles:
                data = KuroWavesUserInfo.model_validate(role)
                if data.gameId != WAVES_GAME_ID:
                    continue
                res = await WavesBind.insert_waves_uid(
                    ev.user_id, ev.bot_id, data.roleId, ev.group_id, lenth_limit=9
                )
                if res == 0 or res == -2:
                    await WavesBind.switch_uid_by_game(
                        ev.user_id, ev.bot_id, data.roleId
                    )
                waves_msg.append(f"[鸣潮]已刷新特征码【{data.roleId}】")

        if pgr_roles:
            for role in pgr_roles:
                data = KuroWavesUserInfo.model_validate(role)
                if data.gameId != PGR_GAME_ID:
                    continue
                res = await WavesBind.insert_uid(
                    ev.user_id,
                    ev.bot_id,
                    data.roleId,
                    ev.group_id,
                    lenth_limit=None,
                    game_name="pgr",
                )
                if res == 0 or res == -2:
                    await WavesBind.switch_uid_by_game(
                        ev.user_id, ev.bot_id, data.roleId, game_name="pgr"
                    )
                pgr_msg.append(f"[战双]已刷新特征码【{data.roleId}】")

        if waves_msg or pgr_msg:
            break

    if not waves_msg and not pgr_msg:
        if invalid:
            return "刷新绑定失败，token已失效，请重新登录后再试\n"
        return "刷新绑定失败，请确认token有效后重试\n"

    return "\n".join(waves_msg + pgr_msg)


async def delete_cookie(ev: Event, uid: str) -> str:
    count = await WavesUser.delete_cookie(uid, ev.user_id, ev.bot_id)
    if count == 0:
        return f"[鸣潮] 特征码[{uid}]的token删除失败!\n❌不存在该特征码的token!\n"
    return f"[鸣潮] 特征码[{uid}]的token删除成功!\n"


async def get_cookie(bot: Bot, ev: Event) -> Union[List[str], str]:
    uid_list = await WavesBind.get_uid_list_by_game(ev.user_id, ev.bot_id)
    if uid_list is None:
        return ERROR_CODE[WAVES_CODE_103]

    msg = []
    for uid in uid_list:
        waves_user: Optional[WavesUser] = await WavesUser.select_waves_user(
            uid, ev.user_id, ev.bot_id
        )
        if not waves_user:
            continue

        ck = await waves_api.get_self_waves_ck(uid, ev.user_id, ev.bot_id)
        if not ck:
            continue
        msg.append(f"鸣潮uid: {uid} 的 token 和 did")
        msg.append(f"添加token {waves_user.cookie}, {waves_user.did}")
        msg.append("--------------------------------")
        
    if not msg:
        return "您当前未绑定token或者token已全部失效\n"
    
    msg.append("直接复制并加上前缀即可用于token登录")

    return msg
