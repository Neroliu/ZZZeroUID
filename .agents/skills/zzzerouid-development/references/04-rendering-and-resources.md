# 四、渲染与资源

> 返回 [SKILL.md](../SKILL.md)

出图以 **PIL** 为主，素材在各模块 `texture2d/` 与 `utils/texture2d/`。
字体：`utils/fonts/zzz_fonts.py`。

路径单源：`utils/resource/RESOURCE_PATH.py`（`MAIN_PATH`、`PLAYER_PATH`、`RESOURCE_PATH`、
角色/音擎/驱动盘/邦布/阵营图标、`CAT_GUIDE_PATH` / `FLOWER_GUIDE_PATH`）。

启动下载：`zzzerouid_resource` + `utils/resource/download_all_resource.py`。
离线生成地图：`tools/data_to_map.py`、`data_to_map_by_hakush.py`。

攻略：配置 `ZZZGuideProvide`。文件名 = `alias_to_char_name` 后的角色名 + `.jpg/.png`。
缺失时返回「该角色攻略不存在」。

评分：`zzzerouid_char_detail/official_score.py`，对照 `docs/API与官方评分说明.md` 与 `test/verify_official_score.py`。
改公式不要只改绘制层。
