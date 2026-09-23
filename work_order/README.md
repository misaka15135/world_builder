# 工单索引与协作流程

更新日期：2026-09-23。

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
| 008 | [Unity 场景导出与加载验证](008_unity_export.md) | planned | 待认领 | 005；完整验收 006、007 |
| 009 | [Minecraft Java 区域导出](009_minecraft_schematic_export.md) | planned | 待认领 | 005；完整验收 006、007 |
| 010 | [Minecraft Java 独立世界导出](010_minecraft_world_export.md) | planned | 待认领 | 009 |
| 011 | [IFC 建筑概念模型验证](011_ifc_concept_export.md) | planned | 待认领 | 005、006；游戏首版之后 |
| 012 | [大区域与资源扩展验证](012_large_world_benchmarks.md) | planned | 待认领 | 006、007、008、009 |

下一个可分配编号：013。编号由协调者串行分配，避免并行碰撞。

当前状态：001—005 done。006 in_progress：已交付 128 m 固定规格生成/存档恢复与有限楼梯修复、建筑预留空间反馈；44 项测试通过，v2 小范围输入首次 15/30、最终 30/30。后续继续模型接口、已接受响应保存及正式包协议。007—012 尚未开始，完整城邦扩规模前仍需 008/009 的样件转换。010 为必要性待明确的可选后续路线。

## 执行约定

1. 读取索引、总规划和相关工单。
2. 确认依赖与文件所有权，登记执行者和状态。
3. 按验收标准实施，完成动作立即记录；完成条目同时勾选和划掉。
4. 记录验证命令、结果或文档证据，不将设计目标描述为已实现能力。
5. 阶段结束更新工单、索引和总规划；明确下一步。

新工单使用 [模板](TEMPLATE.md)。研究与方案交付物放在 `docs/`，工单记录计划、状态、动作和证据。
