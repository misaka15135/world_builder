# 历史工单与承接映射

归档日期：2026-10-29；由用户授权的 047 工单系统重构产生。001—046 停止作为当前排期入口，原编号、正文、完成标记和状态均保留为归档时快照；只重定位相对链接。旧状态 in_progress/planned 不表示仍在执行，也不改写成 done/cancelled。

当前只执行 [首页](../README.md) 的五张主线。以下“承接”表示未完成工作转入新范围，不表示实现完成；不在主线的要求进入有启动条件的 BACKLOG。新单的验收门槛是当前接受标准，历史记录按原日期/版本解释。

[旧总规划](legacy/000_project_master_plan.md)和[旧索引](legacy/README.md)保留原始上下文；它们不是当前任务入口。机器清单与完整性摘要见 [registry.json](../registry.json)。旧正文与快照不再追加执行记录，修订说明写在当前工单。

| 旧编号 | 历史记录 | 归档时状态 | 原未完成项数 | 当前承接/用途 |
|---|---|---|---|---|
| 001 | [问题重述与正式方案](legacy/001_problem_and_proposal.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 002 | [分层生成可行性调研](legacy/002_generation_research.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 003 | [世界元数据与跨目标导出调研](legacy/003_representation_research.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 004 | [方案独立审查](legacy/004_proposal_review.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 005 | [WIR v0.1 数据契约与样例](legacy/005_wir_contract.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 006 | [最小分层生成闭环](legacy/006_generation_vertical_slice.md) | in_progress | 7 | [048](../048_agent_foundations.md)、[049](../049_agent_execution.md)、[050](../050_single_building_m1.md)、[051](../051_scene_delivery_m2.md)、[B04](../BACKLOG.md#b04-大规模与性能)、[B05](../BACKLOG.md#b05-复杂几何与高级场景能力) |
| 007 | [本地三维查看与增量编辑](legacy/007_local_viewer_editor.md) | planned | 7 | [052](../052_scene_revision_m3.md)、[B01](../BACKLOG.md#b01-完整手工编辑器) |
| 008 | [Unity 场景导出与加载验证](legacy/008_unity_export.md) | in_progress | 6 | [050](../050_single_building_m1.md)、[051](../051_scene_delivery_m2.md)、[052](../052_scene_revision_m3.md)、[B04](../BACKLOG.md#b04-大规模与性能) |
| 009 | [Minecraft Java 区域导出](legacy/009_minecraft_schematic_export.md) | in_progress | 8 | [050](../050_single_building_m1.md)、[051](../051_scene_delivery_m2.md)、[B02](../BACKLOG.md#b02-Minecraft 独立存档) |
| 010 | [Minecraft Java 独立世界导出](legacy/010_minecraft_world_export.md) | planned | 5 | [B02](../BACKLOG.md#b02-Minecraft 独立存档) |
| 011 | [IFC 建筑概念模型验证](legacy/011_ifc_concept_export.md) | planned | 7 | [B03](../BACKLOG.md#b03-IFC 专业扩展) |
| 012 | [大区域与资源扩展验证](legacy/012_large_world_benchmarks.md) | planned | 6 | [B04](../BACKLOG.md#b04-大规模与性能) |
| 013 | [场景简报（流水线 A）](legacy/013_scene_brief.md) | in_progress | 0 | [051](../051_scene_delivery_m2.md) |
| 014 | [地形方案（流水线 B）](legacy/014_terrain_plan.md) | in_progress | 2 | [051](../051_scene_delivery_m2.md)、[B05](../BACKLOG.md#b05-复杂几何与高级场景能力) |
| 015 | [风物目录与背景包（流水线 C）](legacy/015_landmark_catalogue.md) | in_progress | 1 | [051](../051_scene_delivery_m2.md) |
| 016 | [区块归属与选址（流水线 D）](legacy/016_district_siting.md) | in_progress | 1 | [051](../051_scene_delivery_m2.md)、[B05](../BACKLOG.md#b05-复杂几何与高级场景能力) |
| 017 | [单栋建筑设计器（流水线 E）](legacy/017_building_designer.md) | in_progress | 2 | [050](../050_single_building_m1.md)、[051](../051_scene_delivery_m2.md)、[B05](../BACKLOG.md#b05-复杂几何与高级场景能力) |
| 018 | [装配器与场景流水线（流水线 F）](legacy/018_assembler_pipeline.md) | in_progress | 2 | [049](../049_agent_execution.md)、[050](../050_single_building_m1.md)、[051](../051_scene_delivery_m2.md) |
| 019 | [Minecraft 本机启动恢复](legacy/019_minecraft_recovery.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 020 | [场景道路走廊栅格化与地面填充顺序](legacy/020_scene_corridor_rasterization.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 021 | [风格建筑双目标样件](legacy/021_style_building_cross_target_sample.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 022 | [新存档四场景重构](legacy/022_scene_reconstruction_new_world.md) | in_progress | 0 | [051](../051_scene_delivery_m2.md)、[B07](../BACKLOG.md#b07-历史证据专项核对) |
| 023 | [API 模型驱动的 A—F 多智能体流水线](legacy/023_api_agent_pipeline.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 024 | [API 多智能体真实服务与目标平台验收](legacy/024_api_agent_live_evaluation.md) | planned | 10 | [050](../050_single_building_m1.md)、[051](../051_scene_delivery_m2.md)、[052](../052_scene_revision_m3.md)、[B07](../BACKLOG.md#b07-历史证据专项核对) |
| 025 | [模块化本地应用与网页测试台](legacy/025_modular_web_workbench.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 026 | [Windows 桌面应用初版](legacy/026_windows_desktop_application.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 027 | [本地主线与验证分支职责调整](legacy/027_branch_role_alignment.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 028 | [场景搭建后续工单规划](legacy/028_followup_work_order_planning.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 029 | [通用场景需求与任务契约](legacy/029_scene_task_contracts.md) | planned | 10 | [048](../048_agent_foundations.md) |
| 030 | [能力驱动的任务调度与作用域返工](legacy/030_capability_task_runtime.md) | planned | 11 | [049](../049_agent_execution.md)、[051](../051_scene_delivery_m2.md) |
| 031 | [自然景观资产与分布构建](legacy/031_natural_scene_assets.md) | planned | 8 | [051](../051_scene_delivery_m2.md) |
| 032 | [稳定世界身份与任务依赖存储](legacy/032_world_revision_identity.md) | planned | 9 | [048](../048_agent_foundations.md)、[052](../052_scene_revision_m3.md) |
| 033 | [用户修改指令与局部再生成](legacy/033_scoped_scene_revision.md) | planned | 9 | [052](../052_scene_revision_m3.md) |
| 034 | [场景反馈与修订工作台](legacy/034_feedback_workbench.md) | planned | 9 | [052](../052_scene_revision_m3.md) |
| 035 | [目标平台能力配置与后续平台选型](legacy/035_target_profiles_and_selection.md) | planned | 8 | [048](../048_agent_foundations.md)、[B06](../BACKLOG.md#b06-下一游戏平台) |
| 036 | [Unity 与 Minecraft 通用场景适配](legacy/036_unity_minecraft_scene_adapters.md) | planned | 9 | [050](../050_single_building_m1.md)、[051](../051_scene_delivery_m2.md) |
| 037 | [下一游戏平台场景适配原型](legacy/037_next_game_scene_adapter.md) | planned | 6 | [B06](../BACKLOG.md#b06-下一游戏平台) |
| 038 | [历史工单证据与当前职责核对](legacy/038_historical_work_order_reconciliation.md) | planned | 6 | [047](../047_work_order_restructure.md)、[B07](../BACKLOG.md#b07-历史证据专项核对) |
| 039 | [核心文档与协作入口对齐](legacy/039_core_document_alignment.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 040 | [全部更改推送与远端分支职责同步](legacy/040_remote_branch_publication.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 041 | [Agent 客户端 Figma 交互与界面概念稿](legacy/041_client_figma_concept.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 042 | [Agent 目标架构与迁移文档对齐](legacy/042_agent_architecture_document_alignment.md) | done | 0 | 历史成果/设计依据，仅按需引用 |
| 043 | [模型行动协议适配与能力检测](legacy/043_model_action_adapters.md) | planned | 5 | [049](../049_agent_execution.md) |
| 044 | [工具网关与 MCP 接入](legacy/044_tool_gateway_mcp.md) | planned | 6 | [049](../049_agent_execution.md) |
| 045 | [任务上下文与专业知识检索](legacy/045_context_knowledge_retrieval.md) | planned | 6 | [051](../051_scene_delivery_m2.md) |
| 046 | [建筑构建工具与候选预览闭环](legacy/046_building_tool_loop.md) | planned | 6 | [050](../050_single_building_m1.md) |

旧任务中未勾选项保留在完整记录中；复用时须核对后续证据，不把过期未勾选自动认定为当前缺陷。已完成记录不重复实施，功能证据不足保持未验。归档哈希用于发现意外修改，不替代功能验收。
