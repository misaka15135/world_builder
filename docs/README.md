# 项目文档索引

更新日期：2026-10-11。先辨明文档描述的是当前目标、现有行为还是历史证据，再用于设计和执行。

## 当前入口

| 文档 | 用途 |
|---|---|
| [00 当前项目基线](00_project_baseline.md) | 产品目的、场景边界、当前原型、后续架构与负责工单 |
| [05 Agent 流水线](05_api_agent_pipeline.md) | 当前 0.1.0 固定 A—F 的运行、API、回放与限制 |
| [06 网页测试台](06_web_workbench.md) | HTTP API v1、只读预览、任务与历史管理 |
| [07 桌面应用](07_desktop_application.md) | Windows 0.1.0 便携包、数据目录、依赖和构建 |
| [08 真实 API 首批评估](08_live_evaluation_024.md) | 024 的 DeepSeek 四例预登记、预算、无回显密钥输入及分层验收 |
| [Agent JSON 契约](contracts/api-agents-v0.1.md) | 023 已实现的严格请求/响应与几何规则 |
| [WIR 契约](contracts/wir-v0.1.md) / [存储入口](../storage/README.md) | 源世界、版本、事务、资源与交换边界 |
| [工单索引](../work_order/README.md) / [总规划](../work_order/000_project_master_plan.md) | 任务状态、依赖、验收与当前实施顺序 |

文档中的版本按其各自模块理解：Agent 0.1.0、WIR 0.1、HTTP API v1 和桌面 0.1.0 不是一次统一升级。029 等后续工单尚未改变当前 Schema、运行 skills 或 API。

## 早期方案与研究

| 文档 | 日期与适用范围 |
|---|---|
| [01 问题重述](01_problem_restatement.md) | 2026-09-21 需求基线；原始城邦优先级与工程扩展阶段保留作历史 |
| [02 可行性研究](02_feasibility.md) | 2026-09-21 文献证据及设计判断；不是今天的实现/性能验收 |
| [03 正式方案](03_formal_proposal.md) | 2026-09-21 混合架构方案；规则规划默认、旧阶段预算不再作为当前路线 |
| [04 流水线重构](04_scene_pipeline.md) | 2026-09-26 旧规则控制面诊断；不能代替 023 的实现契约或 029—037 的新设计 |
| [生成证据](research/002_generation_evidence.md) / [表示证据](research/003_representation_evidence.md) / [独立审查](research/004_review.md) | 按原访问日期、证据等级及适用边界引用；没有在本轮重新调研或复现 |

## 契约与目标验证的使用边界

[模块接口](contracts/module-interfaces.md) 与 [目标能力矩阵](contracts/target-capability-matrix.md)包含跨模块设计约定，不能据此断言全部功能已实现。实际 Agent 行为以当前契约、Schema、代码与对应验收证据为准；稳定身份/修改接口和 target profile 分别在 032/033 与 035 落地。

[006 运行说明](contracts/generation-v0.1.md)、scene-brief/terrain/districts/building-design/scene-assembly 契约，以及 Unity/Minecraft 样件、城邦、开放空间记录描述旧规则路线或独立样件。它们可提供复用依据，不证明新 Agent 场景通过了目标验收。实际环境的历史记录见 [环境基准](contracts/environment-baseline.md)。

[WIR 权威与打包 ADR](adr/0001-wir-authority-and-packaging.md)继续适用：WIR 为源数据，平台文件为派生产物。IFC 的技术记录仅用于独立专业扩展，不是当前游戏场景路线的必经门槛。
