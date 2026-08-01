from pathlib import Path

from PIL import Image, ImageDraw

from gsuid_core.models import Event
from gsuid_core.utils.image.convert import convert_img
from gsuid_core.utils.download_resource.download_file import download

from ..utils.hint import error_reply
from ..utils.image import (
    GREY,
    YELLOW,
    BLACK_G,
    add_footer,
    get_zzz_bg,
    get_player_card_min,
)
from ..utils.api.models import Boss, ListItem
from ..utils.zzzero_api import zzz_api
from ..utils.fonts.zzz_fonts import (
    zzz_font_38,
    zzz_font_50,
    zzz_font_54,
    zzz_font_thin,
)
from ..utils.resource.RESOURCE_PATH import TEMP_PATH, BBS_T_PATH, MONSTER_PATH
from ..zzzerouid_roleinfo.draw_role_info import draw_avatar, draw_bangboo

TEXT_PATH = Path(__file__).parent / "texture2d"
boss_mask = Image.open(TEXT_PATH / "monster_mask.png")
boss_fg = Image.open(TEXT_PATH / "monster_fg.png")

CARD_HEIGHT = 420
HARD_SECTION_GAP = 120


def get_rank_tier(percent: int | float) -> Image.Image:
    rank_percent = percent
    color: tuple[int, int, int] | str = BLACK_G
    if rank_percent <= 1:
        rank_tag = "tier_5"
    elif rank_percent <= 10:
        rank_tag = "tier_4"
    elif rank_percent <= 25:
        rank_tag = "tier_3"
    elif rank_percent <= 50:
        rank_tag = "tier_2"
    else:
        color = "white"
        rank_tag = "tier_1"

    rank_img = Image.open(TEXT_PATH / f"{rank_tag}.png").convert("RGBA")

    rank_draw = ImageDraw.Draw(rank_img)
    rank_draw.text(
        (140, 49),
        f"{rank_percent:.2f}%",
        font=zzz_font_38,
        fill=color,
        anchor="mm",
    )

    return rank_img


async def draw_boss(boss: Boss) -> Image.Image:
    boss_card = Image.new("RGBA", (241, 333))

    boss_name = boss["name"]
    boss_race = boss["race_icon"]
    race_name = boss_race.split("/")[-1]
    boss_icon = boss["icon"]
    boss_bg = boss["bg_icon"]
    boss_bg_name = boss_bg.split("/")[-1]

    bg_path = BBS_T_PATH / boss_bg_name
    if not bg_path.exists():
        await download(boss_bg, BBS_T_PATH, boss_bg_name)
    bg_img = Image.open(bg_path).resize((241, 333))

    boss_path = MONSTER_PATH / f"{boss_name}.png"
    if "?" in boss_name or "？" in boss_name:
        boss_name = boss_icon.split("/")[-1].split(".")[0]
        boss_path = MONSTER_PATH / f"{boss_name}.png"

    if not boss_path.exists():
        await download(boss_icon, MONSTER_PATH, f"{boss_name}.png")
    boss_img = Image.open(boss_path).resize((241, 333))

    bg_img.paste(boss_img, (0, 0), boss_img)

    if boss_race:
        race_path = TEMP_PATH / race_name
        if not race_path.exists():
            await download(boss_race, TEMP_PATH, race_name)
        race_img = Image.open(race_path).resize((110, 110))
        bg_img.paste(race_img, (115, 212), race_img)

    bg_img.paste(boss_fg, (0, 0), boss_fg)

    boss_card.paste(bg_img, (0, 0), boss_mask)
    return boss_card


async def draw_mem_card(mem: ListItem) -> Image.Image:
    card = Image.open(TEXT_PATH / "card_bg.png")
    card_draw = ImageDraw.Draw(card)

    star_full = Image.open(TEXT_PATH / "star_full.png")
    star_empty = Image.open(TEXT_PATH / "star_empty.png")

    _time = mem["challenge_time"]
    time_str1 = f"{_time['year']}.{_time['month']}.{_time['day']}"
    time_str2 = f"{_time['hour']}:{_time['minute']}:{_time['second']}"
    time_str = f"通关时刻 {time_str1} {time_str2}"

    boss_img = await draw_boss(mem["boss"][0])
    card.paste(boss_img, (62, 51), boss_img)

    card_draw.text(
        (333, 91),
        mem["boss"][0]["name"],
        font=zzz_font_54,
        fill=YELLOW,
        anchor="lm",
    )
    card_draw.text(
        (333, 155),
        f"{mem['score']}",
        font=zzz_font_50,
        fill="white",
        anchor="lm",
    )
    card_draw.text(
        (333, 202),
        time_str,
        font=zzz_font_thin(20),
        fill=GREY,
        anchor="lm",
    )

    mem_star = mem["star"]
    for j in range(3):
        star_img = star_full if j < mem_star else star_empty
        card.paste(star_img, (515 + j * 30, 133), star_img)

    if mem["buffer"]:
        buff = mem["buffer"][0]
        buff_icon = buff["icon"]
        buff_name = buff_icon.split("/")[-1]
        buff_path = TEMP_PATH / buff_name
        if not buff_path.exists():
            await download(buff_icon, TEMP_PATH, buff_name)
        buff_img = Image.open(buff_path).resize((78, 78))
        card.paste(buff_img, (851, 13), buff_img)

    for aindex, agent in enumerate(mem["avatar_list"]):
        avatar_img = await draw_avatar(agent)
        avatar_img = avatar_img.resize((152, 176))
        card.paste(avatar_img, (320 + aindex * 146, 221), avatar_img)

    bangboo_img = await draw_bangboo(mem["buddy"])
    bangboo_img = bangboo_img.resize((123, 143))
    card.paste(bangboo_img, (770, 251), bangboo_img)

    return card


async def draw_mem_img(uid: str, ev: Event, schedule_type: int) -> str | bytes:
    data = await zzz_api.get_zzz_mem_info(uid, schedule_type)
    if isinstance(data, int):
        return error_reply(data)

    normal_list = data["list"]
    hard_list = data["hard_list"] if data["has_hard"] else []

    if not data["has_data"] or (not normal_list and not hard_list):
        return "你还没有挑战本期【危局强袭战】/或数据未刷新!\n可尝试使用【上期强袭战】查询上期战绩！"

    player_card = await get_player_card_min(uid, ev)
    if isinstance(player_card, int):
        return error_reply(player_card)

    w = 950
    h = 730 + CARD_HEIGHT * len(normal_list)
    if hard_list:
        h += HARD_SECTION_GAP + CARD_HEIGHT * len(hard_list)

    rank_img = get_rank_tier(data["rank_percent"] / 100)
    all_score = data["total_score"]
    all_star = data["total_star"]

    img = get_zzz_bg(w, h, "bg4")
    title = Image.open(TEXT_PATH / "title.png")
    title_draw = ImageDraw.Draw(title)
    title_draw.text(
        (368, 94),
        f"{all_score}",
        font=zzz_font_50,
        fill="white",
        anchor="mm",
        stroke_width=2,
        stroke_fill="black",
    )
    title.paste(rank_img, (424, 45), rank_img)
    img.paste(title, (0, -11), title)

    banner = Image.open(TEXT_PATH / "banner.png")
    bar = Image.open(TEXT_PATH / "bar.png")
    bar_draw = ImageDraw.Draw(bar)
    bar_draw.text(
        (807, 217),
        f"x{all_star}",
        font=zzz_font_38,
        fill="white",
        anchor="lm",
    )
    img.paste(bar, (0, 264), bar)
    img.paste(player_card, (0, 330), player_card)
    img.paste(banner, (0, 552), banner)

    y_offset = 660
    for mem in normal_list:
        card = await draw_mem_card(mem)
        img.paste(card, (0, y_offset), card)
        y_offset += CARD_HEIGHT

    if hard_list:
        hard_banner = Image.new("RGBA", (950, HARD_SECTION_GAP), (0, 0, 0, 0))
        hard_draw = ImageDraw.Draw(hard_banner)

        hard_draw.text(
            (80, 55),
            "绝境难度",
            font=zzz_font_50,
            fill=YELLOW,
            anchor="lm",
            stroke_width=2,
            stroke_fill="black",
        )

        hard_score = sum(i["score"] for i in hard_list)
        hard_star = sum(i["star"] for i in hard_list)
        hard_draw.text(
            (320, 55),
            f"{hard_score}",
            font=zzz_font_38,
            fill="white",
            anchor="lm",
            stroke_width=2,
            stroke_fill="black",
        )
        hard_draw.text(
            (480, 55),
            f"★x{hard_star}",
            font=zzz_font_38,
            fill="white",
            anchor="lm",
        )

        hard_rank_img = get_rank_tier(data["hard_rank_percent"] / 100)
        hard_banner.paste(hard_rank_img, (620, 10), hard_rank_img)

        img.paste(hard_banner, (0, y_offset), hard_banner)
        y_offset += HARD_SECTION_GAP

        for mem in hard_list:
            card = await draw_mem_card(mem)
            img.paste(card, (0, y_offset), card)
            y_offset += CARD_HEIGHT

    img = add_footer(img)
    return await convert_img(img)
