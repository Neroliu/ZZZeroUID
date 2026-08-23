# 三、绑定、API、面板数据

> 返回 [SKILL.md](../SKILL.md)

## 绑定

```python
from ..zzzerouid_config.zzzero_config import ZZZ_GAME_NAME  # "zzz"
await GsBind.insert_uid(qid, ev.bot_id, uid, ev.group_id, game_name=ZZZ_GAME_NAME)
```

`utils/uid.py::get_uid`：

- 从文本抽 `\d{8,10}`
- 否则 `GsBind.get_uid_by_game(..., "zzz")`
- 命令在 `ZZZIgnoreAt` 里且存在 `ev.at` → **raise Exception**（会先 `bot.send` 提示）

## API

米游社 Record 前缀 `ZZZ_API`（国服）/ HoYoLAB OS。
主要路径在 `utils/api/api.py`：`/index` `/note` `/avatar/info` `/challenge` `/abyss_abstract`
`/hadal_info_v2` `/hadal_mem_detail_v2` `/void_front_battle_detail` `/zenkov_abstract_info` 等。

面板外源：

- Enka：`https://enka.network/api/zzz/uid/{}`
- MiniGG：`https://profile.microgg.cn/api/zzz/uid/{}`

刷新：`zzzerouid_char_detail/refresh_char_detail.py` 按 `RefreshDataList` 依次试。

抽卡：`PUBLIC_API` `getGachaLog`。

## 本插件表

`utils/database/model.py`：`ZzzPush`（体力阈值、是否已推）。WebConsole `ZzzPushAdmin`。
UID 仍在 `GsBind`。
