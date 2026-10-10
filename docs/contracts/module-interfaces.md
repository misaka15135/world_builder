# WIR 0.1 模块接口

适用范围（2026-10-10）：下文是 005 冻结的跨模块接口设计，不代表各模块都已实现。当前 Agent 请求/响应见 [0.1.0 契约](api-agents-v0.1.md)，网页现有接口见 [HTTP API v1](../06_web_workbench.md)。稳定世界/对象身份、增量命令与用户修改由 [032](../../work_order/032_world_revision_identity.md) / [033](../../work_order/033_scoped_scene_revision.md) 后续实现；IFC 是独立可选扩展。本轮不变更接口字段或 Schema。

本文件固定 006—011 之间的最小边界。传输结构必须携带 `contract_version: "0.1.0"`；不支持的主版本或必需能力应明确拒绝。

## 规划器

输入：`base_revision_id`、作用域实体 ID、结构化 `WorldSpec`、适用约束、目标 profile ID、稳定 seed、生成器版本和资源预算。输出：新增/修改/删除记录组成的候选差异、读取依赖、写入作用域、任务 outcome、资源统计和验证请求。

规划器不直接移动分支头，不修改锁定字段，不把目标平台文件作为源数据。候选仅在独立验证和存储事务成功后成为新修订。

## 验证器

输入：基础修订、候选差异、验证规则集、作用域及边界邻域。输出：每条约束的 pass/fail/unknown、涉及实体、容差、诊断、可选修复建议和实际检查范围。

验证器必须是只读且可重复的。候选违反硬约束只证明候选无效；只有规则直接矛盾或完备求解器证明无解时，任务 outcome 才能写 `infeasible`。

## 存储与编辑命令

领域命令包含 `operation_id`、`base_revision_id`、目标 ID、命令类型、参数和作者。存储层检查基础修订、锁、引用和候选验证摘要；成功时在事务中创建新修订并比较交换分支头。版本不匹配时返回冲突，不自动覆盖。

## 适配器

输入：不可变 `revision_id`、选区、要求的语义完整度、目标 profile 和输出预算。输出：派生文件、对象映射、目标验证结果和 `export_report`。适配器不得修改 WIR；目标工具中的修改也不自动回写。

Unity、Minecraft 与 IFC 适配器共享稳定 ID 和损失分类，不共享隐式坐标假设。每个适配器负责自己的坐标矩阵、量化、材料/构件映射和目标版本检查。

## 失败合同

统一错误包含稳定 `code`、`message`、`scope_ids`、`retryable` 和可选 `details`。最低错误族为：

- `contract.*`：Schema、能力或版本错误。
- `reference.*`、`graph.*`、`geometry.*`：WIR 语义错误。
- `constraint.*`：约束未通过或无法确定。
- `conflict.*`：基础修订或锁冲突。
- `resource.*`：资源缺失、哈希错误或许可元数据缺失。
- `target.*`：目标版本、能力或导入验证失败。
- `execution.*`：超时、预算、取消和实现错误。

调用方按 `code` 和 `retryable` 决策，不解析人类可读消息。
