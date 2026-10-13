# 场景需求分型契约 0.2.0-draft.1

状态：029 的独立、可执行草案；**不是当前 API 入口**。当前运行仍使用 [0.1.0 固定 A—F 契约](api-agents-v0.1.md)。本草案只验证需求与跨阶段身份/类别引用，不运行模型、不调度任务、不编译 WIR。

## 数据边界

- 长度为 m，右手坐标 X 东、Y 北、Z 上。`region_m` 必须与调用方 32—512 m、16 m 整数倍区域一致；版本、单位、坐标字段必须显式匹配。未定义新几何原语或旋转。
- A 需求类别：`site`（需独立场地和建筑/构筑物设计）、`road_network`（道路/通行网络）、`interior_space`（隶属某一 `site` 需求）、`terrain_condition`、`natural_object`。`necessity` 为 `required` 或 `optional`；site、interior 和 natural 用非负的场景总数量上下界表达。数量不是每栋配额，密度与面积单位留待 029 后续版本明确。
- 只有 `site.min_count` 占 `max_sites`。道路、房间、地形和自然对象不能通过增加场地预算来容纳。`road_network.connects` 只能引用 site 需求，森林零建筑时可为空。室内需求的 `parent_site_id` 必须引用允许室内的 site 需求。
- 关系和验收条件只能引用已声明需求；每个必需需求都须有验收条件。模型自称满足条件不等于目标侧验收完成。

## 跨阶段引用投影

[需求 Schema](../../schemas/scene-brief-0.2.0-draft.1.schema.json)和[引用投影 Schema](../../schemas/scene-links-0.2.0-draft.1.schema.json)由 [`scene_requirements.py`](../../src/world_builder/agents/scene_requirements.py)生成并校验。引用投影是后续 C/D/E 产物的最小身份摘要，不是新版完整阶段响应：

| 投影字段 | 允许引用 |
|---|---|
| `catalogue` | `site` 或 `natural_object` 同类别需求；道路不得变成 C 场地目录项 |
| `sites` | `site` 类 catalogue；实际数量满足对应需求并受 `max_sites` 限制 |
| `roads` | `road_network` 需求；必需道路不得缺席 |
| `interior_spaces` | `interior_space` 需求和归属正确的场地实例 |
| `natural_objects` | `natural_object` 类 catalogue；数量满足对应需求 |

所有对象 ID 必须唯一。未知类别、交叉引用、错版本、缺少必需对象和超过数量范围均拒绝；验证器不自动转换、删除或补造对象。地形、道路真实连通、室内通行、自然资产存在性、用户原文语义和几何仍须后续专门校验，不能由此投影证明。

人工正例位于 [`scene_requirements_v02.json`](../../examples/scene_requirements_v02.json)：街景、零建筑零道路的森林溪流、含小屋的林地营地。其作用是离线契约回归，不是模型质量或目标导出证据。运行 `python tools/write_agent_contracts.py --check` 与 `python -m pytest tests/test_scene_requirements.py -q` 校验 Schema 同步和正负例。

## 兼容和下一步

0.1.0 的 Schema、响应 fixture、回放和现有 WIR 编译器不变；0.1.0 需求因无新版类别与版本字段会被本草案显式拒绝。不能在两个版本之间默默重标类别。029 还需定义任务建议/依赖/能力、密度单位、C/D/E/F 的完整 payload 与有效空集合等；030 在此后实现上游返修和动态调度，035 提供目标能力输入。只有连接运行时并完成新批次真实 API 验证后，才能声称道路误作场地的问题在产品流程中得到改善。
