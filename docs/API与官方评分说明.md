# ZZZeroUID API 与官方评分说明

> 基于米游社战绩 HAR（2026-08）与当前插件实现整理。  
> Base（国服）：`https://api-takumi-record.mihoyo.com/event/game_record_zzz/api/zzz`

---

## 1. 驱动盘官方评分

### 1.1 要不要单独拉评分接口？

**不需要。** 官方评分附在角色详情接口返回值中：

```http
GET /avatar/info?id_list[]={avatar_id}&server={region}&role_id={uid}
```

关键字段：

| 路径 | 含义 |
|------|------|
| `avatar_list[i].equip_plan_info` | 方案 + 总命中 + 评级 |
| `equip_plan_info.valid_property_cnt` | 有效副属性共命中次数 |
| `equip_plan_info.equip_rating` | 如 `ER_S` |
| `equip_plan_info.equip_rating_score` | 服务端连续分（如 77.17） |
| `equip_plan_info.plan_effective_property_list` | 有效副属性（长 ID） |
| `equip[].properties[].valid` / `add` / `level` | 单条是否有效、强化次数、档位 |
| `equip[].invalid_property_cnt` / `all_hit` | 未命中次数 / 是否满命中 |

插件刷新面板（MYS）时已调用该接口，查询面板只读本地 JSON，**无额外请求**。

### 1.2 Enka / 旧本地数据如何处理？

Enka / MiniGG **不提供** `equip_plan_info` 与真实 `valid`；更早的本地 JSON 也可能缺 `level`/`add`/`valid`。

插件策略：

1. **任意用户**用 **MYS** 刷新某角色 → 将该角色的「有效副属性规则」写入全局缓存：  
   `{资源目录}/ZZZeroUID/official_equip_plan.json`  
   （只缓存规则，不缓存某玩家的命中数/评级。）

2. **Enka 刷新 / 查询旧存档**时调用 `ensure_official_score`：  
   - 已有完整 `equip_plan_info`（旧 MYS 存档）：写缓存，必要时补 `valid` / 未命中  
   - 盘上已有 `valid=true`（残缺 plan）：按词条回算命中并合成简易 plan  
   - 否则用全局规则缓存回算：  
     - `valid`：`property_id ∈ plan_effective_property_list`  
     - 命中：`sum(level where valid)`  
     - 未命中：`sum(add where not valid)`  
   - 回算成功会**写回**该角色本地 JSON，避免每次查询重复兼容  

3. 本地回算**不伪造** `equip_rating`（服务端算法未公开）；展示命中次数 + 词条有效性，并标注来源。

4. 无规则且无缓存时：分数显示 `--`，不把 Enka 的全 `valid=false` 当成废词条灰显。

实现文件：

- `zzzerouid_char_detail/official_score.py` — 缓存读写与回算  
- `zzzerouid_char_detail/refresh_char_detail.py` — 刷新时写缓存 / 回算  
- `zzzerouid_char_detail/draw_new_char_detail_card.py` — 绘制  

> 旧文件 `utils/map/PartnerScore.json` 已废弃，代码不再读取。

### 1.3 属性 ID 注意

- 面板总属性短 ID：`1` 生命 / `2` 攻击 / `5` 暴击…  
- 驱动盘词条长 ID：`12102` 攻击力百分比 / `20103` 暴击率…  
- 有效与否必须以 **property_id** 为准，不能只看中文名（「攻击力」固定值与百分比同名）。

---

## 2. 迷宫诡域

```http
GET /zenkov_abstract_info?region={region}&uid={uid}
```

| 项目 | 状态 |
|------|------|
| `api.py` 常量 | `ZZZ_ZENKOV_API` |
| `models.py` | `ZZZZenkovData` 等 |
| `request.py` | `get_zzz_zenkov_info(uid)` |
| 命令 / 绘图 C 端 | **未实现** |

字段概要：赛季等级、周常 duty、累计带出、地图列表、排名、珍品图鉴等。详见历史分析 `test/迷宫诡域与驱动盘评分_API整理.md`。

调用示例：

```python
from ZZZeroUID.utils.zzzero_api import zzz_api

data = await zzz_api.get_zzz_zenkov_info(uid)
```

---

## 3. 战绩 API 接入总览

| Path | 插件接入 | 说明 |
|------|----------|------|
| `/index` | ✅ `get_zzz_index_info` | 主页；stats 大量字段可再挖 |
| `/note` | ✅ | 便签 |
| `/widget` | ✅ | 小组件便签 |
| `/avatar/basic` | ✅ | 角色列表 |
| `/avatar/info` | ✅ | 角色详情 + **官方评分** |
| `/buddy/info` | ✅ | 邦布 |
| `/challenge` | ✅ | 旧挑战 |
| `/hadal_info_v2` | ✅ | 式舆防卫 |
| `/hadal_mem_detail_v2` | ✅ | 危局强袭详情 |
| `/abyss_abstract` | ✅ | 深渊摘要（旧） |
| `/void_front_battle_detail` | ✅ | 虚无前线详情（`void_front_id` 现写死） |
| `/zenkov_abstract_info` | ✅ 仅 API | 迷宫诡域摘要 |
| `/month_info`（nap_ledger） | ✅ | 绳网月报 |
| 抽卡 log / 公告 | ✅ | 另路径 |

### 3.1 HAR 中有、尚未接入（或仅部分用）的接口

| Path | 建议优先级 | 用途 |
|------|------------|------|
| `/abysss2_abstract` | 高 | 深渊二期（等级/任务/收藏/特遣等） |
| `/exploration_detail` | 高 | 区域收集 + 猫咪笔记完整图鉴 |
| `/holo_boss_detail` | 高 | 拟境湮灭 |
| `/gacha_calendar` | 中高 | 角色/音擎卡池日历 |
| `/activity_calendar` | 中 | 活动列表与进度 |
| `/void_front_battle_period_abstract_info` | 中 | 虚无前线期数摘要，可拿动态 `void_front_id` |
| `/climbing_tower_detail` | 中 | 爬塔 s1–s4（index 已有 brief） |
| `/hadal_mem_abstract_info` | 中 | 危局轻量摘要 |
| `/share_award_status` | 低 | 分享奖励 |

### 3.2 index.stats 可增强（无需新接口）

`zenkov_brief`、`holo_boss_brief`、`void_front_brief`、`hadal_brief`、`climbing_tower_s*`、`game_data_show`（称号/勋章）、`temple_data`、`rab_brief` 等。

---

## 4. 插件内 API 常量与方法对照

| 常量 (`utils/api/api.py`) | 方法 (`request.py`) |
|---------------------------|---------------------|
| `ZZZ_INDEX_API` | `get_zzz_index_info` |
| `ZZZ_NOTE_API` | `get_zzz_note_info` |
| `ZZZ_NOTE_WIDGET_API` | `get_zzz_widget_info` |
| `ZZZ_AVATAR_BASIC_API` | `get_zzz_avatar_basic_info` |
| `ZZZ_AVATAR_INFO_API` | `get_zzz_avatar_info` |
| `ZZZ_BUDDY_INFO_API` | `get_zzz_bangboo_info` |
| `ZZZ_CHALLENGE_API` | `get_zzz_challenge_info` |
| `ZZZ_HADAL_API` | `get_zzz_hadal_info` |
| `ZZZ_MEM` | `get_zzz_mem_info` |
| `ZZZ_ABYSS_API` | `get_zzz_abyss_info` |
| `ZZZ_VOID_BATTLE_API` | `get_zzz_void_info` |
| `ZZZ_ZENKOV_API` | `get_zzz_zenkov_info` |
| `ZZZ_MONTH_INFO` | `get_zzz_month_info` |

统一入口：`from ZZZeroUID.utils.zzzero_api import zzz_api`。

---

## 5. 面板展示约定（当前实现）

1. **布局坐标与改版前一致**（weapon `y=949`，equip `y=1397`，伤害 `y=2460`），驱动盘与武器区原设计重叠衔接，**不再插入独立评分条**以免错位。  
2. **命中摘要**写在 `equip_bg` 顶部原有空白（约 y=40~80），不改变 paste 位置。  
3. **单盘徽章**：仅「满命中」或「未命中 N」；无规则时 `--`。  
4. **武器区总评**：`N次`；有 MYS 官方 `equip_rating` 时再贴 S/A/B 图标（回算不贴伪造字母）。  
5. **副属性**：仅在有可信评分时按 `valid` 高亮并显示 `+N`。

---

## 6. 维护提示

- 想丰富全局评分规则库：引导用户用 **米游社 Cookie（MYS）刷新面板**。  
- 缓存文件可备份/迁移：`official_equip_plan.json`。  
- 新角色首次仅有人 MYS 刷过，Enka 用户才能回算该角色评分。  
- `equip_rating` 字母级仅在有 MYS 原始字段时展示，避免误导。
