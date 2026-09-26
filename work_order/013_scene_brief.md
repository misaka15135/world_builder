# 013 场景简报（流水线 A）

- 状态：in_progress
- 创建日期：2026-09-26
- 执行者：待认领
- 依赖：005（WIR 0.1 与规格字段约定）；不依赖 006 的实现
- 修改范围：未来的 `world_builder/planning/brief.py`、`settings/<name>/setting.json`、`tests/test_brief.py`、`docs/contracts/scene-brief-v0.1.md`

## 目标与范围

把"用户说要造什么"从一句自由文本变成**结构化简报**，作为整条流水线（B—F）的唯一入口。这是用户规划里的 A。

现状对照：今天的入口是 `source_prompt` 加一次模型调用，且模型被限制只能回 6 个字段（`scenario`、`building_count`、`interior_count`、`layout_profile`、`lock_stair_void`），既没有背景（魔法城邦/现代都市/工业园/港口），也没有"必须出现哪些风物"这种可验收的要求。详见 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md) §2。

本工单只做简报与背景包的**数据契约**，不做地形、风物目录或建筑本身。

## 输入输出契约

`SceneBrief`（JSON，带单位与上限）至少包含：

| 字段 | 含义 |
|---|---|
| `setting` | 背景标识，如 `arcane_medieval`、`modern_metropolis`、`industrial_park`、`harbour` |
| `era` | 时代/技术档，用于材质、交通与建筑词汇 |
| `scale_m` | 目标区域边长（米）与建筑数量区间 |
| `mood` | 基调（如"拥挤的边境小镇""规整的 CBD"），供 B/C 解释 |
| `required_landmarks` | 必现风物：类型、数量、优先级（可空则视为无硬性要求） |
| `targets` | 目标平台与导出精度（unity / minecraft / viewer / ifc） |
| `budget` | 时间与（可选的）模型调用上限 |

同时定义**背景包**目录结构：`settings/<setting>/setting.json`（本工单）、`terrain.json`（014）、`catalogue.json`（015）、`designs/*.json`（017）。

## 工作项

- [x] ~~定义 `SceneBrief` 的 Schema、必填/可空规则、数值上限与单位（米/平方米/层）。~~
- [x] ~~定义背景包目录结构与加载/校验入口；缺字段时报明确错误，不静默补默认值。~~
- [x] ~~用确定性规则实现"自由文本 → 简报"的离线版本（关键词与模板），并保留模型版本的同契约接口。~~
- [x] ~~为 4 个目标背景各写一份 `setting.json` 初稿：魔法城邦、现代大都市、工业产业园、港口。~~
- [x] ~~简报本身的校验规则：必现风物非空（当用户明确要求时）、数量与尺度在上限内、背景标识已注册。~~

模型路径的**接口与本地 fixture 已实现**（`brief_from_response`、`FixtureBriefProvider`、`examples/brief_model_response.json`），真实云服务仍未接入——这属于用户决策（供应商与额度），与本工单的离线验收无关。

## 验收标准

- 同一段自然语言输入两次得到完全一致的简报（离线路径），并可回放已接受结果。
- 四份背景包初稿都能通过 Schema 校验，且 `required_landmarks` 能明显区分四个背景（例如魔法城邦含城堡/公会/教堂，港口含码头/货轮/仓库）。
- 简报→背景包的加载失败（缺字段、未知背景）有明确错误码，不产生半成品世界。
- 前置的 128 m 试验与 512 m 城邦路径不受影响（旧规格字段与世界身份不变）。

## 明确不做

- 不做地形判断（014）、风物尺寸细节（015）、选址（016）。
- 不接入真实云模型服务：模型实现只写接口与本地 fixture，供应商与额度由用户决定后再启用。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-26 | root | 根据用户对流水线的重构要求创建本工单 | 本文件与 [docs/04_scene_pipeline.md](../docs/04_scene_pipeline.md)；尚无实现或测试结果 | 认领后先冻结 `SceneBrief` Schema 再写四个背景包 |
| 2026-09-26 | root | 实现阶段 A：简报 Schema、背景包加载、离线规则编译器、模型合同 | 新增 `src/world_builder/planning/{brief,catalogue}.py`、`settings/*/{setting,catalogue}.json`、`tools/compile_brief.py`、`examples/brief_model_response.json`、`tests/test_scene_brief.py`（16 passed）与 [合同文档](../docs/contracts/scene-brief-v0.1.md)。实测：`--prompt "河谷里的魔法城邦，要有城堡、冒险者工会和教堂"` → `arcane_medieval`、`brief_digest sha256:3715a9d7…`、有效需求 7 项、`not_designed_yet` 明确列出城堡/城墙/行会/广场；同一输入两次结果完全一致；fixture 模型响应走同一套校验并写入 `accepted_response_hash` | 由 015 补齐风物目录（已同轮完成），随后 014 地形 |

## 交接说明

开始前重读 000、docs/04、本工单与 005 的规格字段约定，登记实际文件范围。完成每个有结果的动作后更新执行记录；通过验收后用 `- [x] ~~工作描述~~` 划掉对应条目。
