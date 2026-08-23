# 五、配置、订阅、启动

> 返回 [SKILL.md](../SKILL.md)

## 配置

`ZZZ_CONFIG = StringConfig("ZZZeroUID", CONFIG_PATH, CONFIG_DEFAULT)`

| 键 | 作用 |
|----|------|
| `ZZZPrefix` | 展示用前缀（真正匹配仍看 Plugins / WebConsole） |
| `ZZZIgnoreAt` | 这些命令禁止 @ |
| `SignTime` / `SchedSignin` | 自动签到 |
| `SchedEnergyPush` | 定时电量 |
| `WidgetResin` | 便签改组件 API |
| `CrazyNotice` | 催命推送 |
| `RefreshBG` / `RefreshCardUsePic` / `EnableCustomCharBG` | 面板外观 |
| `ZZZGuideProvide` | 猫冬 / 听雨惊花 |
| `RefreshDataList` | ENKA / MINIGG / MYS 顺序 |

## 订阅

`gs_subscribe` 任务名：`[绝区零] 推送`、`[绝区零] 体力`、`[绝区零] 自动签到`、`[绝区零] 自动清红`。
开关在 `zzzerouid_config/__init__.py`。电量检查 `zzzerouid_stamina/notice.py`。

## 启动 / 帮助

`@on_core_start` → `zzzerouid_resource.startup`。
`register_help("ZZZeroUID", f"{prefix}帮助", Image.open(ICON))`。
