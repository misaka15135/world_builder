# 10 应用接口、事件与契约草案

日期：2026-11-11。版本：design-2026-11-11。以下 `/api/design/` 是用于评审的占位命名空间，当前服务未实现；不覆盖现有 HTTP v1、Agent 0.1.0 或 WIR 0.1。

## 1. 接口层次与访问权

| 接口 | 调用者 | 接受者 | 权限 |
|---|---|---|---|
| HTTP 命令/查询 | 本地已认证工作台 | Application Service | 创建、修改、取消、明确选择、导出 |
| ModelPort | Runtime | 供应商适配器 | 返回统一 Action，无工具执行权 |
| ToolPort | Gateway | 内置 worker / 受限 MCP | 在声明 scope 内读或写候选 |
| CommitPort | 受信任应用/运行时 | Repository | 原子接受，拒绝模型直接调用 |
| EventPort | 后端持久事件 | 工作台 / 运行审计 | 展示事件，不作为新指令执行 |

`submit_candidate` 仅提交候选审查请求。用户的接受命令表示在既定权限内请求本地接受，仍须通过锁、版本、硬约束与取消检查；不能以客户端 `force=true` 绕过。

## 2. 通用信封与版本

请求包含 `contract_version`；写命令使用 `Idempotency-Key`，基于世界状态的命令携带 `base_revision_id` 和 `expected_head_generation`。同一幂等键和规范化请求摘要返回原响应；同键不同内容返回 `IDEMPOTENCY_CONFLICT`。键作用域为本地项目、调用者身份、操作类型，不跨用户复用。

标识符为不透明字符串，客户端不能从 ID 推断时间、权限或对象内容。时间为 UTC RFC3339；UI 本地化展示。长度单位为 m，坐标为 RH X 东/Y 北/Z 上；资产原始单位只存在于导入记录，不能污染标准数据。

未知主版本拒绝；向后兼容字段只在明确扩展容器中增加。工具输入使用它自己的版本化 Schema，顶层 Action 校验不代替参数、引用、作用域、预算与跨字段语义校验。

## 3. HTTP 接口目录

全部路径以 `/api/design` 为前缀。请求成功表示服务接收或返回状态，不意味着目标平台验收成功。

| 方法与路径 | 主要输入 | 响应 | 特殊规则 |
|---|---|---|---|
| GET `/capabilities` | profile/协议过滤 | 已启用能力及版本 | 区分 supported、experimental、unavailable |
| POST `/connections/probe` | endpoint、credential_ref、model、protocol | ProbeReport | 禁止在结果返回密钥；探测可能消耗用户配置预算 |
| POST `/worlds` | 名称、源版本、空世界配置 | 201 World | 分配稳定 world_id；无模型调用 |
| GET `/worlds/{world_id}` | 无 | World + ETag | 包含 head_revision_id、head_generation |
| POST `/worlds/{world_id}/operations` | intent、base、scope、targets、budget | 202 Operation | 原子持久化后才进入队列 |
| GET `/operations/{operation_id}` | 无 | Operation、任务摘要 | 预算分 estimated/observed/unknown |
| POST `/operations/{operation_id}/cancel` | expected_state_version | 202 状态 | 取消幂等；与提交竞争以事务顺序判定 |
| POST `/operations/{operation_id}/answers` | question_id、question_version、answer | 200 状态 | 过期问题 409；超时不能自动回答 |
| GET `/operations/{operation_id}/events` | after、limit | EventPage | 有序持久游标；分页和背压 |
| GET `/worlds/{world_id}/revisions` | cursor、limit | RevisionPage | 返回不可变版本元数据 |
| GET `/worlds/{world_id}/objects` | revision、bounds、ids、limit | ObjectPage | 绑定快照；大几何只返回引用 |
| GET `/candidates/{candidate_id}` | 无 | CandidateSummary | 明确基础修订与验证状态 |
| POST `/candidates/{candidate_id}/accept` | base、expected generation、validation_hash | 200 Revision | 服务端重新判定；禁止接受未验候选 |
| POST `/worlds/{world_id}/locks` | object/field/region、expected lock version | LockSet | 锁由用户命令建立，模型不能解锁 |
| POST `/worlds/{world_id}/history/restore` | revision_id、expected head、reason | World | 复用历史快照并创建审计修订，检查锁冲突；无模型调用 |
| POST `/worlds/{world_id}/exports` | revision_id、profile_id、profile_hash、loss_policy | 202 ExportJob | 不接受未冻结候选作为正式导出 |
| GET `/artifacts/{artifact_id}` | 无 | 资源字节与摘要 | 项目授权、内容类型、大小与安全下载名 |

为避免伪装成完整已发布契约，机器可读 [OpenAPI 草案](contracts/openapi.design.json)仅冻结三个关键评审接口：启动 Operation、取消、接受候选。其余目录接口在 048/052 冻结时补齐完整 Schema 与兼容策略。

## 4. Action 与 ToolResult

Action 字段：`contract_version, operation_id, task_id, action_id, type, payload`。允许类型及 payload：

| type | 必填 payload | 处理 |
|---|---|---|
| tool_call | call_id、tool_name、tool_version、arguments | 网关检查与执行；结果进入观察 |
| submit_candidate | candidate_id | 进入 validating；不接受任意新 JSON 作为已验几何 |
| request_replan | reason、affected_task_ids | 运行时检查作用域、必需项、预算并创建新任务版本 |
| request_input | question、options | 持久化待答问题；运行时生成 question_id/version |
| report_gap | capability、reason | 记录能力缺口，阻断依赖任务或等待明确需求调整 |

原生工具调用由适配器转换为相同 Action；行动 JSON 经过严格解析转换；旧 `json_contract` 不走此结构。供应商原始调用 ID 可另存映射，不能替代服务端 `call_id` 唯一性。

ToolResult 最小字段为 `call_id, tool_name, tool_version, status, output_refs, diagnostics, usage, receipt_ref`。`status` 属于 succeeded/failed/unknown/cancelled；queued/running 是执行账本状态，不作为最终观察成功。失败仍需准确归档已发生副作用和可重试条件。诊断可包含 `code, severity, message, object_ids, location, constraint_id, expected, actual, retryable`；不得把内部异常堆栈直接回传模型。

## 5. 错误与幂等语义

| HTTP / code | 场景 | 自动处理 |
|---|---|---|
| 400 MALFORMED_REQUEST | JSON/信封无法解析 | 不重试；用户/适配器修正 |
| 401 SESSION_REQUIRED | 令牌过期 | 重新建立本地会话 |
| 403 SCOPE_DENIED / LOCKED | 权限、锁或工具未授权 | 不自动放宽 |
| 404 NOT_FOUND | 引用不存在或不可访问 | 不从名称猜测 ID |
| 409 STALE_BASE / DEPENDENCY_CONFLICT | 世界头、读依赖、空间冲突 | 展示差异，新候选重新验证 |
| 409 IDEMPOTENCY_CONFLICT | 同键不同摘要 | 使用新的用户命令，不重放旧键 |
| 412 PRECONDITION_FAILED | ETag / 锁版本不匹配 | 刷新状态再明确提交 |
| 413 RESOURCE_LIMIT | 输入/资产/输出超限 | 减少授权范围或调整预算 |
| 422 INVALID_GRAPH / VALIDATION_FAILED | Schema 或领域约束不满足 | 有预算的受限修正 |
| 429 BUDGET_EXCEEDED / RATE_LIMITED | 本地额度或供应商限制 | 本地额度不自动增加；限流按预算退避 |
| 503 DEPENDENCY_UNAVAILABLE | 外部服务故障 | 只按幂等声明重试 |

错误统一包含 `code, message, request_id, retryable, diagnostics`，可选 `resource_ref`。不返回密钥、文件系统绝对路径或未脱敏供应商正文。

## 6. 事件、游标和一致性

Event 包含 `event_id, sequence, operation_id, task_id?, type, occurred_at, payload_ref?, summary`。`sequence` 在 Operation 内严格递增，唯一约束 `(operation_id,sequence)`。类型包括 operation.created、task.state_changed、tool.receipt、candidate.ready、revision.accepted、budget.changed、question.opened、operation.finished。

提交世界和写入 `revision.accepted` 事件在同一数据库事务完成；网络推送可重复，UI 按 event_id 去重。UI 初次读取状态快照与一致游标，再读取 `after`；连接断开按游标恢复。游标已被保留策略清理返回明确错误和重新同步入口，不默默跳过。大数据引用加载受权限检查，摘要不代替事实记录。

首版分页轮询足够；SSE 为可替换传输，不能用无法设置令牌头的客户端方式暴露令牌到 URL。推送缓存不是事实库。

## 7. 缓存键与资源一致性

模型请求缓存仅用于明确回放或等价输入复用：包括协议、模型、提示/Skill 版本、实际读取资源摘要、工具白名单、profile 与约束摘要。不能只用全局描述散列替代局部依赖。几何缓存包含算法版本、规范化参数、资产摘要和坐标版本。导出缓存包含 revision 内容、profile/adapter版本、资源清单和 loss_policy。

工具执行结果只有声明可复用且作用域、读版本相同时才能复用；命中仍产生引用原回执的审计事件。未知执行状态不能缓存成失败或成功。

## 8. 可执行样例与限制

[Action Schema](contracts/action.schema.json)、[有效行动](examples/actions.valid.json)、[无效行动](examples/actions.invalid.json)与[三类场景任务图](examples/scenario_graphs.json)供评审和契约验证。无效例包括未知动作、缺 call_id、额外越权字段；任务图例包括无建筑森林及遗漏必需项/依赖环反例。

验证脚本只证明草案结构和图覆盖规则，不证明真实模型理解、工具执行、几何构建、数据库恢复或目标加载。048 需将冻结后的字段迁入正式契约并补领域测试，049 需验证两协议产生同一语义，050—052 分阶段运行真实批次。
