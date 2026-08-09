import json
import random
from typing import Any, Dict, List, Union, Optional
from pathlib import Path

import aiofiles
from PIL import Image, ImageDraw

from gsuid_core.sv import get_plugin_available_prefix
from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img

from .utils import (
    BLUE,
    YELLOW,
    CUSTOM_LEFT,
    INVALID_GREY,
    CUSTOM_OFFSET,
    WEAPON_EQUIP_POS,
    get_skill_dict,
    map_equip_rating,
    get_equip_plan_info,
    get_effective_display_names,
)
from .dmg_cal import get_dmg
from ..utils.image import (
    add_footer,
    get_zzz_bg,
    get_pro_img,
    get_camp_img,
    get_prop_img,
    get_rank_img,
    get_equip_img,
    get_rarity_img,
    get_element_img,
    get_mind_role_img,
    get_player_card_min,
)
from .official_score import (
    ensure_official_score,
    has_official_mys_plan,
    supplement_official_score_from_mys,
)
from ..utils.name_convert import char_name_to_char_id
from ..utils.fonts.zzz_fonts import (
    zzz_font_28,
    zzz_font_30,
    zzz_font_40,
    zzz_font_50,
    zzz_font_thin,
)
from ..utils.resource.download_file import get_weapon
from ..utils.resource.RESOURCE_PATH import CUSTOM_PATH, PLAYER_PATH
from ..zzzerouid_config.zzzero_config import ZZZ_CONFIG

is_custom = ZZZ_CONFIG.get_config("EnableCustomCharBG").data
TEXT_PATH = Path(__file__).parent / "texture2d"
STAR_PATH = TEXT_PATH / "star"

prop_id_to_icon = {
    "1": "IconHpMax",
    "2": "IconAttack",
    "3": "IconDef",
    "4": "IconBreakStun",
    "5": "IconCrit",
    "6": "IconCritDam",
    "7": "IconElementAbnormalPower",
    "8": "IconElementMystery",
    "9": "IconPenRatio",
    "10": "IconPenValue",
    "11": "IconSpRecover",
    "12": "IconSpGetRatio",
    "13": "IconSpMax",
    "19": "IconSheerForce",
    "232": "IconPenValue",
    "315": "IconPhysDmg",
    "316": "IconFire",
    "317": "IconIce",
    "318": "IconThunder",
    "319": "IconDungeonBuffEther",
}


def _format_prop_value(prop: Dict[str, Any]) -> str:
    final = prop.get("final", "")
    if isinstance(final, str):
        return final
    return f"{final:.1f}"


def _equip_name_display(name: str) -> str:
    if len(name) >= 3 and name[-1] == "]" and "[" in name:
        return name[: name.rfind("[")]
    return name


def _score_source_tag(plan: Dict[str, Any]) -> str:
    if plan.get("_score_source") == "cache_computed":
        return "缓存回算"
    if plan.get("_score_source") == "legacy_valids":
        return "旧数据"
    if (plan.get("cultivate_info") or {}).get("name") == "cache_computed":
        return "缓存回算"
    if (plan.get("cultivate_info") or {}).get("name") == "legacy_valids":
        return "旧数据"
    return ""


def _has_scoring_valids(equips: List[Dict[str, Any]], plan: Optional[Dict[str, Any]]) -> bool:
    """是否具备可信的 valid 评分（避免 Enka 全 False 被当成已评分）。"""
    if not plan:
        return False
    if any(p.get("valid") is True for eq in equips if "id" in eq for p in (eq.get("properties") or [])):
        return True
    # MYS 原装可能全有效但仍有 equip_rating
    if plan.get("equip_rating") and plan.get("_score_source") not in (
        "cache_computed",
        "legacy_valids",
    ):
        return True
    if plan.get("valid_property_cnt") and plan.get("equip_rating"):
        return True
    # 缓存回算后可能 0 命中但仍有 plan
    if plan.get("_score_source") in ("cache_computed", "legacy_valids"):
        return True
    if (plan.get("cultivate_info") or {}).get("name") in (
        "cache_computed",
        "legacy_valids",
    ):
        return True
    return False


async def draw_char_detail_img(uid: str, ev: Event, char: str) -> Union[str, bytes]:
    char_id = char_name_to_char_id(char)
    if not char_id:
        return f"[绝区零] 角色名{char}无法找到, 可能暂未适配, 请先检查输入是否正确！"

    path = PLAYER_PATH / str(uid) / f"{char_id}.json"
    if not path.exists():
        prefix = get_plugin_available_prefix("ZZZeroUID")
        return f"[绝区零] 未找到该角色信息, 请先使用[{prefix}刷新面板]进行刷新!"

    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        data = json.loads(await f.read())

    # 1) 本地规则缓存回算（无 Cookie 也能用别人刷过的规则）
    data = ensure_official_score(data)

    # 2) 本地仍无 MYS 官方 plan → 查询时拉一次 MYS 补分并写回缓存
    #    （解决：刷新走 ENKA 优先、从未落盘 equip_plan_info）
    if not has_official_mys_plan(data):
        patched = await supplement_official_score_from_mys(uid, [data])
        if patched:
            data = patched[0]

    need_save = bool(
        data.pop("_official_score_applied", False)
        or data.pop("_score_merged_from_mys", False)
    )
    if need_save:
        try:
            # 去掉仅内存标记；equip_plan_info 整段保留
            save_data = {
                k: v
                for k, v in data.items()
                if k
                not in (
                    "_official_score_applied",
                    "_score_merged_from_mys",
                )
            }
            async with aiofiles.open(path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(save_data, ensure_ascii=False, indent=4))
            data = save_data
        except Exception:
            pass

    plan = get_equip_plan_info(data)
    effective_names = get_effective_display_names(plan)
    official_rank = map_equip_rating(plan.get("equip_rating", "") if plan else "")
    valid_hit_total = int(plan.get("valid_property_cnt", 0) or 0) if plan else 0
    is_cache_score = bool(_score_source_tag(plan) if plan else "")
    source_tag = _score_source_tag(plan) if plan else ""

    dmg = get_dmg(data)
    # 恢复与改版前一致的总高度，避免驱动盘/伤害区错位
    img = get_zzz_bg(1100, 2525 + 58 * len(dmg), "bg3")

    # 角色部分
    char_bg = Image.new("RGBA", (1100, 770))
    set_custom = False

    if is_custom:
        custom_char_path = CUSTOM_PATH / char_id
        if custom_char_path.exists():
            pic_list = list(custom_char_path.glob("*.[jp][pn]g"))
            if pic_list:
                random_pic = random.choice(pic_list)
                char_img = Image.open(random_pic).convert("RGBA")
                char_img = char_img.resize((1313, 770))
                char_bg.paste(char_img, (-120, 0), char_img)
                set_custom = True

    if not set_custom:
        char_img = get_mind_role_img(char_id).convert("RGBA")
        _w = char_img.size[0] * 0.94
        _h = char_img.size[1] * 0.94
        new_size = int(_w), int(_h)
        char_img = char_img.resize(new_size)
        if char_id in CUSTOM_OFFSET:
            _box = CUSTOM_OFFSET[char_id]
        else:
            _box = (int(550 - _w // 2 - 235), -128)
        char_bg.paste(char_img, _box, char_img)

    img.paste(char_bg, (0, 195), char_bg)

    # title部分
    title = Image.open(TEXT_PATH / "title.png")
    player_card = await get_player_card_min(uid, ev)
    title.paste(player_card, (-63, 65), player_card)
    title_draw = ImageDraw.Draw(title)
    avatar_name = data["name_mi18n"]
    level = data["level"]
    profession = data["avatar_profession"]

    pro_icon = get_pro_img(profession, 70, 70)
    element_icon = get_element_img(data["element_type"], 70, 70)

    title_draw.text(
        (918, 131),
        avatar_name,
        "white",
        zzz_font_50,
        "rm",
    )

    rank = data["rank"]
    for r in range(rank + 1):
        if r == 0:
            continue
        rank_icon = Image.open(TEXT_PATH / "ranks" / f"{r}.png")
        rank_icon = rank_icon.resize((31, 31)).convert("RGBA")
        title.paste(rank_icon, (737 + 34 * (r - 1), 184), rank_icon)

    title_draw.text((1013, 198), f"Lv.{level}", "white", zzz_font_30, "mm")
    title.paste(pro_icon, (937, 97), pro_icon)
    title.paste(element_icon, (1009, 97), element_icon)
    img.paste(title, (0, -56), title)

    # 属性部分
    props = data["properties"]
    property_bg = Image.open(TEXT_PATH / "prop_bg.png")
    property_draw = ImageDraw.Draw(property_bg)

    pindex = 0
    for prop in props:
        prop_name: str = prop["property_name"]
        prop_name = prop_name.replace("属性伤害", "伤")
        pid = str(prop["property_id"])

        if pid in prop_id_to_icon:
            icon = get_prop_img(prop_id_to_icon[pid], 50, 50)
        else:
            icon = get_prop_img(prop["property_id"], 50, 50)

        property_bg.paste(icon, (53, 3 + int(pindex * 59.6)), icon)

        value = _format_prop_value(prop)
        y = int(27.8 + pindex * 58.6)
        property_draw.text(
            (431, y),
            value,
            "white",
            zzz_font_thin(32),
            "rm",
        )
        property_draw.text(
            (114, y),
            prop_name,
            "white",
            zzz_font_thin(32),
            "lm",
        )
        pindex += 1

    if char_id in CUSTOM_LEFT and not set_custom:
        box = (-6, 230)
    else:
        box = (624, 230)
    img.paste(property_bg, box, property_bg)

    # 技能部分
    skill_dict = get_skill_dict(data)
    skill_bg = Image.open(TEXT_PATH / "skill_bar.png")
    skill_draw = ImageDraw.Draw(skill_bg)
    for skill_pos_num in skill_dict:
        skill_level, skill_color = skill_dict[skill_pos_num]
        skill_draw.text(
            (551 + skill_pos_num * 94, 88),
            f"{skill_level}",
            skill_color,
            zzz_font_28,
            "mm",
        )
    img.paste(skill_bg, (0, 957), skill_bg)

    weapon_bg = Image.open(TEXT_PATH / "weapon_bar.png")

    # 驱动盘
    _equips = data.get("equip") or []
    equips: List[Dict[str, Any]] = []
    for s in range(6):
        for i in _equips:
            if i.get("equipment_type") == s + 1:
                equips.append(i)
                break
        else:
            equips.append({"equipment_type": s + 1})

    scoring_ready = _has_scoring_valids(equips, plan)

    equip_bg = Image.open(TEXT_PATH / "equip_bg.png")
    equip_bg_draw = ImageDraw.Draw(equip_bg)

    # 在 equip_bg 原有标题空白区写短摘要（不改变 paste 坐标，避免与 weapon 错位）
    # equip 卡片从 y≈113 开始，顶部约 0~100 可写字
    if scoring_ready and plan:
        summary = f"有效副属性共命中 {valid_hit_total} 次"
        if source_tag:
            summary = f"{summary} · {source_tag}"
        equip_bg_draw.text(
            (60, 42),
            summary,
            "white",
            zzz_font_thin(26),
            "lm",
        )
        if effective_names:
            name_str = " / ".join(effective_names)
            if len(name_str) > 28:
                name_str = name_str[:27] + "…"
            equip_bg_draw.text(
                (60, 74),
                name_str,
                YELLOW,
                zzz_font_thin(20),
                "lm",
            )
        if official_rank and not is_cache_score:
            rank_img = get_rank_img(official_rank, 52, 52)
            equip_bg.paste(rank_img, (990, 30), rank_img)

    for equip in equips:
        equip_bar = Image.open(TEXT_PATH / "equip_bar.png")
        _type = equip["equipment_type"]
        ox = ((_type - 1) % 3) * 354
        oy = ((_type - 1) // 3) * 458
        if "id" in equip:
            equip_id = equip["id"]
            equip_level = equip["level"]
            equip_name = _equip_name_display(str(equip.get("name") or ""))
            main_props = equip.get("main_properties") or []
            eq_p = equip.get("properties") or []
            if not main_props:
                empty = Image.open(TEXT_PATH / "empty_equip.png")
                equip_bar.paste(empty, (0, 0), empty)
                equip_bg.paste(equip_bar, (-5 + ox, 113 + oy), equip_bar)
                continue

            eq_mp = main_props[0]
            invalid_cnt = int(equip.get("invalid_property_cnt") or 0)
            all_hit = bool(equip.get("all_hit"))

            equip_draw = ImageDraw.Draw(equip_bar)

            equip_draw.text(
                (209, 86),
                f"等级{equip_level}",
                "white",
                zzz_font_thin(20),
                "mm",
            )
            equip_draw.text(
                (160, 145),
                equip_name,
                "white",
                zzz_font_30,
                "mm",
            )

            if equip.get("rarity") == "A":
                equip_color = (177, 0, 255)
            elif equip.get("rarity") == "S":
                equip_color = (255, 146, 0)
            elif equip.get("rarity") == "B":
                equip_color = (0, 167, 255)
            else:
                equip_color = (90, 90, 90)

            equip_img = Image.new("RGBA", (400, 400))
            equip_img_draw = ImageDraw.Draw(equip_img)
            equip_img_draw.ellipse((0, 0, 400, 400), equip_color)
            _equip_img = get_equip_img(equip_id, 380, 380)
            equip_img.paste(_equip_img, (10, 10), _equip_img)

            weapon_equip_img = equip_img.resize((140, 140))
            weapon_equip_pos = WEAPON_EQUIP_POS[_type]
            weapon_bg.paste(
                weapon_equip_img,
                weapon_equip_pos,
                weapon_equip_img,
            )

            equip_img = equip_img.resize((100, 100))

            equip_rarity = get_rarity_img(equip.get("rarity") or "B")
            equip_bar.paste(equip_rarity, (272, 46), equip_rarity)
            equip_bar.paste(equip_img, (22, 0), equip_img)

            equip_draw.rounded_rectangle((71, 186, 350, 231), 8, BLUE)
            mp_img = get_prop_img(eq_mp["property_id"], 38, 38)
            equip_bar.paste(mp_img, (80, 190), mp_img)
            ep_prop_name = str(eq_mp.get("property_name") or "").replace("属性伤害", "伤")
            equip_draw.text(
                (128, 208),
                ep_prop_name,
                "white",
                zzz_font_thin(28),
                "lm",
            )
            equip_draw.text(
                (331, 208),
                str(eq_mp.get("base") or ""),
                "white",
                zzz_font_thin(30),
                "rm",
            )

            for eindex, ep in enumerate(eq_p):
                equip_prop_bar = Image.new("RGBA", (290, 46))
                equip_prop_draw = ImageDraw.Draw(equip_prop_bar)
                equip_prop_draw.rounded_rectangle((5, 4, 285, 42), 8)
                ep_prop_img = get_prop_img(ep["property_id"], 35, 35)
                equip_prop_bar.paste(ep_prop_img, (14, 7), ep_prop_img)

                # 无可信评分时不把 Enka 的 valid=False 画成「废词条灰」
                if scoring_ready:
                    is_valid = bool(ep.get("valid"))
                    ep_color = YELLOW if is_valid else INVALID_GREY
                else:
                    ep_color = "white"

                add_n = int(ep.get("add") or 0)
                prop_label = str(ep.get("property_name") or "")
                if scoring_ready and add_n > 0:
                    prop_label = f"{prop_label} +{add_n}"

                equip_prop_draw.text(
                    (60, 23),
                    prop_label,
                    ep_color,
                    zzz_font_thin(25),
                    "lm",
                )
                equip_prop_draw.text(
                    (266, 23),
                    str(ep.get("base") or ""),
                    ep_color,
                    zzz_font_thin(27),
                    "rm",
                )
                equip_bar.paste(
                    equip_prop_bar,
                    (66, 252 + eindex * 46),
                    equip_prop_bar,
                )

            # 单盘：满命中 / 未命中N；无评分规则时 --
            if scoring_ready:
                if all_hit or invalid_cnt == 0:
                    badge_text = "满命中"
                    badge_color = (255, 196, 1)
                else:
                    badge_text = f"未命中{invalid_cnt}"
                    badge_color = (160, 160, 160)
            else:
                badge_text = "--"
                badge_color = (160, 160, 160)

            badge_w = 110 if len(badge_text) <= 4 else 130
            bx1, bx2 = 350 - badge_w, 350
            equip_draw.rounded_rectangle((bx1, 128, bx2, 162), 10, badge_color)
            equip_draw.text(
                ((bx1 + bx2) // 2, 145),
                badge_text,
                "black",
                zzz_font_thin(20),
                "mm",
            )
        else:
            empty = Image.open(TEXT_PATH / "empty_equip.png")
            equip_bar.paste(empty, (0, 0), empty)
        equip_bg.paste(equip_bar, (-5 + ox, 113 + oy), equip_bar)

    # 与改版前一致：驱动盘贴在 1397（与 weapon 底部设计重叠衔接）
    img.paste(equip_bg, (0, 1397), equip_bg)

    # 武器部分
    weapon = data.get("weapon")
    camp_img = get_camp_img(data["camp_name_mi18n"])
    weapon_draw = ImageDraw.Draw(weapon_bg)
    if weapon:
        weapon_name = weapon["name"]
        weapon_level = weapon["level"]
        main_ps = weapon.get("main_properties") or []
        weapon_ps = weapon.get("properties") or []

        weapon_rank_icon = get_rank_img(weapon.get("rarity") or "B", 64, 64)
        star = int(weapon.get("star") or 0)
        weapon_star_icon = Image.open(STAR_PATH / f"{star}.png")
        weapon_img = await get_weapon(weapon["id"])
        weapon_img = weapon_img.resize((240, 240)).convert("RGBA")

        weapon_bg.paste(weapon_rank_icon, (559, 151), weapon_rank_icon)
        weapon_bg.paste(weapon_star_icon, (643, 216), weapon_star_icon)
        weapon_bg.paste(weapon_img, (140, 157), weapon_img)
        weapon_draw.text((632, 183), weapon_name, "white", zzz_font_40, "lm")
        weapon_draw.text(
            (604, 236),
            f"Lv.{weapon_level}",
            (40, 40, 40),
            zzz_font_28,
            "mm",
        )
        if main_ps:
            main_p = main_ps[0]
            main_prop_id = main_p["property_id"]
            main_prop_img = get_prop_img(main_prop_id, 45, 45)
            weapon_draw.rounded_rectangle((561, 265, 861, 313), 8, BLUE)
            weapon_bg.paste(main_prop_img, (570, 266), main_prop_img)
            weapon_draw.text(
                (620, 289),
                main_p["property_name"],
                "White",
                zzz_font_thin(26),
                "lm",
            )
            weapon_draw.text(
                (842, 289),
                main_p["base"],
                YELLOW,
                zzz_font_thin(30),
                "rm",
            )

        for pindex, p in enumerate(weapon_ps):
            wp_o = pindex * 60
            prop_id = p["property_id"]
            prop_img = get_prop_img(prop_id, 45, 45)
            weapon_draw.rounded_rectangle(
                (561, 326 + wp_o, 861, 374 + wp_o),
                8,
                (40, 40, 40),
            )
            weapon_bg.paste(prop_img, (570, 327 + wp_o), prop_img)

            weapon_draw.text(
                (620, 350 + wp_o),
                p["property_name"],
                "white",
                zzz_font_thin(26),
                "lm",
            )
            weapon_draw.text(
                (842, 350 + wp_o),
                p["base"],
                YELLOW,
                zzz_font_thin(26),
                "rm",
            )

    # 武器区总评：官方字母 +「N次」（布局与旧版一致）
    if official_rank and not is_cache_score:
        weapon_equip_rank = get_rank_img(official_rank, 49, 49)
        weapon_bg.paste(weapon_equip_rank, (563, 437), weapon_equip_rank)
    weapon_bg.paste(camp_img, (875, 156), camp_img)

    if scoring_ready:
        score_label = f"{valid_hit_total}次"
    else:
        score_label = "--"
    weapon_draw.text(
        (739, 448),
        score_label,
        "white",
        zzz_font_40,
        "mm",
    )
    img.paste(weapon_bg, (0, 949), weapon_bg)

    # 伤害部分（原坐标）
    for index, d in enumerate(dmg):
        al = dmg[d]
        d = d.replace("强化特殊技", "强特")
        if len(d) >= 16:
            d = d[:15] + ".."
        bar_index = index % 2 + 1
        dmg_bg = Image.open(TEXT_PATH / f"damage_bar{bar_index}.png")
        dmg_draw = ImageDraw.Draw(dmg_bg)
        dmg_draw.text(
            (97, 31),
            d,
            "white",
            zzz_font_thin(28),
            "lm",
        )
        dmg_draw.text(
            (504, 31),
            al[0],
            "white",
            zzz_font_thin(30),
            "lm",
        )
        dmg_draw.text(
            (698, 31),
            al[1],
            "white",
            zzz_font_thin(30),
            "lm",
        )
        dmg_draw.text(
            (891, 31),
            al[2],
            "white",
            zzz_font_thin(30),
            "lm",
        )
        img.paste(dmg_bg, (0, 2460 + index * 58), dmg_bg)

    img = add_footer(img)
    img = await convert_img(img)
    return img
