# 工单索引与协作流程

更新日期：2026-09-25。

每次工作先阅读本文件、[总规划](000_project_master_plan.md) 和当前工单，再执行任务。具体规则见 [AGENTS.md](../AGENTS.md)。

| 编号 | 工单 | 状态 | 执行者 | 依赖 |
|---|---|---|---|---|
| 000 | [项目总规划](000_project_master_plan.md) | in_progress | 协调者 | 无 |
| 001 | [问题重述与正式方案](001_problem_and_proposal.md) | done | root | 002、003 提供证据 |
| 002 | [分层生成可行性调研](002_generation_research.md) | done | generation_research | 无 |
| 003 | [世界元数据与跨目标导出调研](003_representation_research.md) | done | representation_research | 无 |
| 004 | [方案独立审查](004_proposal_review.md) | done | proposal_review | 001 初稿、002、003 |
| 005 | [WIR v0.1 数据契约与样例](005_wir_contract.md) | done | root | 001—004 |
| 006 | [最小分层生成闭环](006_generation_vertical_slice.md) | in_progress | root | 005 |
| 007 | [本地三维查看与增量编辑](007_local_viewer_editor.md) | planned | 待认领 | 005；最终联调需要 006 |
| 008 | [Unity 场景导出与加载验证](008_unity_export.md) | in_progress | root | 005；完整验收 006、007 |
| 009 | [Minecraft Java 区域导出](009_minecraft_schematic_export.md) | in_progress | root | 005；完整验收 006、007 |
| 010 | [Minecraft Java 独立世界导出](010_minecraft_world_export.md) | planned | 待认领 | 009 |
| 011 | [IFC 建筑概念模型验证](011_ifc_concept_export.md) | planned | 待认领 | 005、006；游戏首版之后 |
| 012 | [大区域与资源扩展验证](012_large_world_benchmarks.md) | planned | 待认领 | 006、007、008、009 |

下一个可分配编号：013。编号由协调者串行分配，避免并行碰撞。

当前状态：001—005 done。006 in_progress：128 m 固定试验已有存档恢复、有限修复、模型规格合同、响应回放和 ZIP64 世界包；独立 512 m、80 栋/5 室内离线源端城邦的预登记输入 30/30 成功、首次 15/30、三类各 10/10。008 in_progress：Unity 6000.3.24f1 两层样件的 26/26 对象/碰撞、方向和连续控制器上楼通过；512 m 城邦 v1 的 176/176 源 ID/碰撞、连续跨桥 3/3 检查点通过；独立 v2 的五栋生成室内导入 346/346 构件/碰撞，首栋 Play Mode 穿门上楼 5/5 检查点通过。全套 Python 回归 71 passed；其余四栋尚未逐栋实走。009 in_progress：Minecraft 1.21.11/Fabric/WorldEdit 版 1363 方块样件由玩家连续走通南门—二层；城邦区域导出仍待做。真实模型服务和复杂地形未验证；007、010—012 未开始。010 为必要性待明确的可选后续路线。

## 执行约定

1. 读取索引、总规划和相关工单。
2. 确认依赖与文件所有权，登记执行者和状态。
3. 按验收标准实施，完成动作立即记录；完成条目同时勾选和划掉。
4. 记录验证命令、结果或文档证据，不将设计目标描述为已实现能力。
5. 阶段结束更新工单、索引和总规划；明确下一步。

新工单使用 [模板](TEMPLATE.md)。研究与方案交付物放在 `docs/`，工单记录计划、状态、动作和证据。
