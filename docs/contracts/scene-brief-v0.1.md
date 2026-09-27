# 场景简报与背景包 0.1

版本：0.1.0。日期：2026-09-26。实现：`src/world_builder/planning/{brief,catalogue}.py`、`settings/*/`、`tools/compile_brief.py`。状态：**离线规则路径已实现并测试；模型路径只有契约与本地 fixture，真实服务未接入。**

本文是流水线阶段 A（[013](../../work_order/013_scene_brief.md)）与阶段 C（[015](../../work_order/015_landmark_catalogue.md)）的合同。方案背景见 [04_scene_pipeline.md](../04_scene_pipeline.md)。

## 1. 为什么先做这两个阶段

整条流水线的输入只有一个：**这份简报**。它必须把"要造什么"写清楚到可验收——背景、时代、尺度、必现风物、目标平台、预算——而不是一句自由文本。风物目录则回答"这个背景应该有哪些建筑与风物"，是后面选址与单栋设计的依据。

两者都是**数据**：新增一个背景＝新增一个目录，不改生成器代码。

## 2. `SceneBrief`

```json
{
  "brief_version": "0.1.0",
  "setting": "arcane_medieval",
  "era": "high_medieval",
  "scale": { "region_m": 512, "buildings": [60, 120] },
  "required_landmarks": [ { "type": "castle", "count": 1, "priority": "must" } ],
  "targets": ["minecraft", "unity", "viewer"],
  "seed": 4,
  "mood": "河谷里的魔法城邦，要有城堡和冒险者工会",
  "notes": "",
  "source_prompt": "…",
  "budget": { "wall_time_ms": 120000, "model_calls": 0 },
  "extensions": {}
}
```

硬性规则（违反即报错，不静默补默认值）：

- `setting` 必须在 `settings/` 存在；`era` 必须在该背景声明的时代里。
- `region_m` 是 128 的整数倍且在 128—4096 之间（与目标分块大小一致）。
- `buildings` 为 `[low, high]`，`1 <= low <= high`。
- 每个 `required_landmarks.type` 必须在该背景的目录里；同一类型不得重复；`count` 不得超过目录声明的上限。
- **背景自身的必现条目也算进建筑预算**：合并后的需求总数不得超过 `buildings` 上限，否则报 `brief.landmark_budget`（与其在阶段 D 才发现排不下，不如在入口就拒绝）。
- `targets` 取自 `minecraft`、`unity`、`viewer`、`ifc`。

错码：`brief.version`、`brief.setting`、`brief.era`、`brief.scale`、`brief.buildings`、`brief.landmarks`、`brief.unknown_landmark`、`brief.duplicate_landmark`、`brief.priority`、`brief.landmark_count`、`brief.landmark_budget`、`brief.targets`、`brief.seed`、`brief.budget`、`brief.prompt`、`brief.setting_unknown`。

`brief.digest()` 给出简报的内容哈希，用于回放与审计。

## 3. 背景包

目录结构：

```text
settings/<setting>/
  setting.json      身份、时代、样式 profile、材质词汇、地形偏好、默认尺度与目标
  catalogue.json    风物目录（本文件定义）
  terrain.json      014 定义（尚未创建）
  designs/*.json    017 定义（尚未创建）
```

`setting.json` 的 `materials` 只允许 `shell`/`floor`/`roof`/`street`/`accent` 五个角色，值是具体方块或材质名，供 017 与目标适配器映射。`terrain_preferences` 是**给 014 的描述性偏好**（可执行的地形 Schema 由 014 定义），因此这里只校验"是字符串映射"，不假装它是地形数据。

2026-09-27 背景包小版本更新：`setting_version` 为 `0.1.1`，新增必填、非空的 `default_prompt`。`assemble_scene.py --setting` 用该提示词编译简报；四个背景的值与预登记 `benchmarks/scene_cases_v1.json` 完全相同。`--prompt` 仍使用用户原文，因此只有两者文本相同时才承诺 WIR 一致；已冻结的批次登记及历史产物不改。

## 4. 风物目录条目

| 字段 | 含义 |
|---|---|
| `type` | 类型标识；同一背景内唯一 |
| `role` | `landmark`/`civic`/`commerce`/`craft`/`housing`/`infrastructure`/`defence`/`green`/`vessel` |
| `required` | 该背景是否默认需要它 |
| `count_range` | 数量区间（必现时下限 ≥ 1） |
| `footprint_m2_range` **或** `linear_m` | 占地面积区间，或线性工程的长度区间（二者只能有一个） |
| `width_m_range` | 仅线性工程需要 |
| `height_m_range` | 高度区间（可选） |
| `adjacency` | 与哪些**站点特征或目录类型**相邻（如 `plaza`、`inn`） |
| `needs` | 场址要求，只能取站点特征：`plaza`/`water`/`coast`/`road`/`rail`/`centre`/`hill`/`gate` |
| `design_state` | `implemented` 或 `planned` |
| `maps_to_programme` | `implemented` 必须填写，且必须是现行生成器真实存在的 programme |
| `silhouette` | 外形基调（给 017 与适配器的提示） |
| `note` | `planned` 必须填写，说明缺什么 |

**`design_state` 是这份合同里最重要的字段。** 它让"我们打算支持"和"现在已经能建"在同一条数据里分开，并且由测试强制：`implemented` 必须指向真实 programme，`planned` 必须写清缺口、且不得声称有映射。目录因此可以一次性写出完整的意图（城堡、摩天楼、码头、货轮），而不会把设计目标读成已实现能力。

## 5. 已知状态（seed 无关，按目录本身统计）

| 背景 | 条目 | 必现 | implemented | planned |
|---|---|---|---|---|
| `arcane_medieval` 魔法中世纪城邦 | 11 | 7 | 7 | 4（行会大厅、广场、城堡、城墙） |
| `modern_metropolis` 现代大都市 | 12 | 9 | 5 | 7（摩天楼、枢纽、地铁、公园、医院、学校、机关） |
| `industrial_park` 工业产业园 | 10 | 6 | 4 | 6（厂房、仓库、储罐、电厂、铁路、货场） |
| `harbour` 港口 | 11 | 9 | 3 | 8（突堤、岸壁、仓库、堆场、船坞、灯塔、海关、货轮） |

`implemented` 的条目全部对应现行生成器的 programme（跨四个背景恰好覆盖全部 9 个），所以这不是新增能力，而是**把已有能力改名、归类并挂到背景上**。真正的缺口在 `planned` 列，属于 017 的工作。

## 6. 两条实现路径

1. **离线规则编译（默认）**：`compile_brief(prompt, seed)`。关键词判定背景与风物，按背景默认尺度缩放，零模型调用、无时钟、无随机，同一输入永远得到同一简报。
2. **模型路径（可选）**：`compile_brief_with_provider(prompt, seed, provider, setting)`。响应必须是 `{contract_version, provider_id, model_id, brief, usage}`，上限 64 KiB，简报仍走**同一套**校验，接受的原始字节哈希写进 `brief.extensions.accepted_response_hash`。仓库内只有一个本地 fixture（`examples/brief_model_response.json`）用于验证合同，真实服务需要用户先定供应商与额度。

模型只产出**计划与数值**：它不能写几何、不能绕过目录、不能把 `planned` 的类型说成已实现。

## 7. 命令行

```powershell
$env:PYTHONPATH = 'src'
python tools/compile_brief.py --prompt "河谷里的魔法城邦，要有城堡、冒险者工会和教堂" --seed 4
python tools/compile_brief.py --prompt "港口，黄昏时分" --setting harbour --response-fixture examples/brief_model_response.json
```

输出包含：简报本体、`brief_digest`、背景摘要（条目/必现/已实现/未实现）、**合并后的有效需求**，以及 `not_designed_yet`——本次需求里还没有设计模板的类型。最后一项是下一阶段（016/017）的待办清单。

## 8. 边界

- 关键词判定是**规则**，不是语义理解：无法识别没有关键词的描述，会明确报 `brief.setting_unknown`，而不是猜一个背景。
- `terrain_preferences` 只是偏好描述，可执行地形由 014 定义；`designs/` 由 017 定义。
- 目录覆盖率不等于真实城市学结论；它是可校验的生成器输入。
