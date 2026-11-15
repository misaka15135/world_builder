# 17 代码组织、关键接口与实施蓝图

日期：2026-11-12。性质：对原设计抽象程度不足的工程补充；推荐方案可直接拆分实现任务，但本章和 SQL 草案不是现有运行实现。精确依赖版本及配置以 [16 技术栈](16_technology_stack.md) 为准；公共行动仍使用 `design-2026-11-11` 草案，正式编号由 048 冻结。

## 1. 实现选型与迁移边界

目标实现使用 Python 3.12、FastAPI/Uvicorn、Pydantic 2、jsonschema、asyncio、HTTPX、SQLite 标准库驱动和官方 MCP SDK。前端采用 React、TypeScript、Vite、Three.js；Windows 宿主延续 pywebview + Edge WebView2，PyInstaller 打包。首版不引入 ORM、Redis、Celery、LangChain 或 LangGraph 作为运行前提。

当前 [server.py](../src/world_builder/workbench/server.py) 是 `ThreadingHTTPServer`，Provider 使用 `urllib`，运行时为固定阶段和线程池，网页是原生 ES Modules 与 Canvas 2D。迁移具体安排为：049 引入新异步应用服务与运行时，保留 `/api/v1` 兼容路由和旧 job/回放读器；050 复用现有 UI 完成单栋闭环；051 升级预览到 Three.js；052 接入 React 完整工作台。不能把前端重写设为 M1 的隐藏前置。

## 2. 包结构与责任映射

以下是建议新增/拆分的目标结构，文件名是实施蓝图，不表示这些文件已经创建：

```text
src/world_builder/
  bootstrap.py                   # 应用组装、模式分流、路径/凭据/生命周期
  api/
    dependencies.py              # 本地会话、服务容器、请求 ID
    errors.py                    # 领域异常到 HTTP 诊断映射
    routers/{worlds,operations,candidates,artifacts,connections}.py
    legacy_v1.py                 # 旧 API 路由与 job 文件读取兼容
  application/
    asgi.py                      # create_app() 工厂、FastAPI lifespan 与依赖组装
    commands.py                  # CreateOperation / Cancel / Accept / Restore
    operation_service.py         # 用户命令幂等与权限边界
    query_service.py             # revision 固定快照查询与分页
  agents/
    contracts/                   # Strict DTO、Action/Observation/TaskGraph
    providers/{base,native_tools,action_json,legacy}.py
    execution/{scheduler,loop,budget,recovery,graph}.py
    context/{assembler,dependency_recorder}.py
  tools/
    registry.py                  # ToolSpec 与版本锁
    gateway.py                   # 权限、参数、预算、回执、输出接受
    workers/{supervisor,protocol,entrypoint}.py
    mcp/{connector,tool_mapper,version_policy}.py
  geometry/
    {terrain,buildings,instances,spatial,validation}.py
  storage/
    repository.py                # 复用并增强现有同步 Repository
    commands.py                  # DB 专用线程的受控命令类型
    executor.py                  # writer 队列与线程内连接管理
    migrations.py                # 显式版本迁移与副本验证
    artifacts.py                 # 资源暂存/摘要/原子发布/GC
  knowledge/{catalog,retrieval,tokenizer,ingest}.py
  export/{service,profiles,evidence}.py
  adapters/{unity,minecraft}/    # 复用现有编码器，外加明确版本的适配入口
  desktop/app.py                 # 现有宿主演进，保留 GUI 主线程
web/                             # 当前兼容工作台，迁移期间保留
frontend/src/
  app/                           # React 路由、布局与错误边界
  api/{client,types,event_cursor}.ts
  features/{connections,operations,worlds,history,export}/
  viewer/{scene,resources,picking,diagnostics,coordinates}.ts
  state/{selection,viewport,preferences}.ts
```

依赖方向固定为 `api → application → execution/domain → ports`，SQLite、HTTP、MCP、worker 是端口实现。`api/routers` 不直接拼装 SQL；`geometry` 不导入 FastAPI/Provider；Three.js 的对象索引不能成为源世界对象库。依赖约束使用静态导入检查进入 CI。

## 3. 核心端口与数据类型

以下为 Python 接口骨架。引用的 DTO 在 `agents/contracts` 中用 Pydantic 严格模型定义，领域内部不可变值可采用 `@dataclass(frozen=True)`；禁止通用 `dict` 在全部层间传递而丢失版本与作用域。

```python
from typing import Protocol
from collections.abc import AsyncIterator

class ModelPort(Protocol):
    async def propose(self, context: ContextBundle,
                      tools: tuple[ToolSpec, ...],
                      limits: ModelCallLimits) -> ModelTurn: ...
    # ModelTurn = normalized actions | refusal | truncation | transport error

class ToolPort(Protocol):
    async def execute(self, call: ToolInvocation,
                      grant: ExecutionGrant) -> ToolResult: ...
    async def receipt(self, call_id: str) -> ReceiptQuery: ...
    async def cancel(self, call_id: str, cancel_epoch: int) -> CancelAck: ...

class WorldQueryPort(Protocol):
    async def query(self, revision: RevisionRef,
                    query: ObjectQuery) -> ObjectPage: ...

class CommitPort(Protocol):
    async def accept(self, command: AcceptCandidate) -> CommitReceipt: ...
    async def restore(self, command: RestoreRevision) -> CommitReceipt: ...

class EventPort(Protocol):
    async def page(self, operation_id: str, after: int,
                   limit: int) -> EventPage: ...

class ArtifactPort(Protocol):
    async def stage(self, metadata: ArtifactMetadata,
                    chunks: AsyncIterator[bytes]) -> StagedArtifact: ...
    async def open(self, artifact: ArtifactRef) -> ArtifactStream: ...
```

| DTO | 关键字段与验证位置 |
|---|---|
| `RevisionRef` | world_id、revision_id、content_hash；查询服务验证同世界引用 |
| `ExecutionGrant` | operation_id、task_id/version、lease_token、cancel_epoch、scope、tool_versions、limits；仅运行时签发 |
| `ToolInvocation` | call_id、tool/version、arguments、规范化参数摘要；绑定持久 ToolCall |
| `AcceptCandidate` | candidate_id、expected_head、expected_head_generation、validation_hash、cancel_epoch、idempotency_key；来自受信任命令服务 |
| `CommitReceipt` | world_id、revision_id、head_generation、operation_id、event_sequence；成功事务后返回 |
| `ReadDependency` | object/field/asset/profile 或空间谓词、版本/结果摘要；由查询/工具实际读取记录 |
| `Diagnostic` | code、severity、constraint_id、object_ids、location、expected、actual、retryable；按 03/10 章归一 |

外部 JSON 先做长度/深度/重复键/有限数值检查，再用封闭 Schema 校验；Pydantic 模型配置 `strict=True`、`extra="forbid"`。Pydantic 用于内部类型和 HTTP DTO，不应静默转换模型输出中的 `"3"` 为整数以掩盖协议错误。行动 Schema 是跨两协议的语义依据，生成的 OpenAPI 是对应用接口的描述，二者不互相替代。

## 4. 控制线程、数据库线程与进程

| 执行单元 | 具体实现 | 不可放入的工作 |
|---|---|---|
| GUI 主线程 | Windows pywebview/WebView2 事件循环 | asyncio.run 后长期占用、模型网络调用、SQLite 写事务 |
| 控制服务线程 | 一个 Uvicorn Server、一个 asyncio loop、`workers=1` | 同步编译、完整 worldpkg 校验、大文件散列 |
| DB writer 专用线程 | 有界 `queue.Queue`，线程内创建/持有 sqlite3 Connection | 网络 I/O、模型调用、跨 `await` 的事务 |
| DB 查询线程 | 有界 ThreadPoolExecutor；各任务在线程内创建/关闭只读连接 | 从别的线程借用 writer Connection |
| 工具子进程 | 显式 worker 入口、有限并发、stdio 受控协议 | 凭据、仓库写连接、任意 shell |

CLI 浏览器模式可在主线程运行 Uvicorn；桌面模式必须将 pywebview 留在主线程，后台控制线程承担同一套 FastAPI 应用。使用 `uvicorn.Server(...).serve()` 受控启动并由宿主发送关闭信号；后台线程不安装与主线程竞争的系统信号处理器。服务 bind 回环地址，端口可用系统分配值，成功监听后才创建窗口。

DB writer 只接受 `RepositoryCommand` 白名单，不接受网络请求提供的任意 SQL/Callable。控制协程提交命令后等待 `Future`，writer 通过 `loop.call_soon_threadsafe` 回送结果。查询使用快照事务保持分页所需 revision 固定；性能昂贵的完整性检查和全包资源读取走后台任务或显式导入验证，不放每个状态查询。

取消一个等待 Future 的协程不等于终止 SQLite 线程或正在执行的工具。取消必须先作为独立持久命令记录 `cancel_epoch`；接受事务再次检查 epoch。事务开始和完成在同一线程、同一 Connection 内，不能把 `BEGIN`、中间查询和 `COMMIT` 分散进多个 `asyncio.to_thread()` 调用。

拟议 API 工厂统一为 `world_builder.application.asgi:create_app`。开发启动命令如下；该模块尚待 049 实现，不能作为当前仓库已可执行入口：

```sh
python -m uvicorn world_builder.application.asgi:create_app --factory --host 127.0.0.1 --port 8765 --workers 1 --loop asyncio --http h11
```

桌面宿主通过同一工厂在后台线程启动 Server，端口由宿主分配；不另起第二个协调者。含真实活跃任务的服务不使用开发热重载，先受控关闭再更新代码。

FastAPI lifespan 管理服务容器与 Scheduler 的启动/停止。`BackgroundTasks` 只适合可丢失的轻量响应后工作，不承载 Operation；Operation 调度事实来自持久任务表、租约和回执，进程重启可以重建。

## 5. 关系数据库草案与接受事务

[repository-extension.design.sql](contracts/repository-extension.design.sql)是可在空数据库执行的逻辑模型，包含 17 张表：connection_probes、worlds、revisions、operations、task_versions、task_dependencies、candidates、candidate_tasks、tool_calls、budget_accounts、budget_reservations、objects、object_versions、revision_objects、locks、spatial_reads、events。它不是针对现有数据库的 `ALTER TABLE` 迁移，不允许直接应用到用户的 `wir.sqlite3`。

| 约束 | SQL 提供的保障 | 服务层还必须执行 |
|---|---|---|
| 世界/修订归属 | 复合外键禁止跨世界 base、parent、result/head | 世界创建在一次事务中完成空初始修订 |
| 世界头代数 | head 变化时 generation 必须加一 | `UPDATE ... WHERE head = expected AND generation = expected` 的 CAS |
| 不可变历史 | Revision/ObjectVersion 更新触发器拒绝覆盖 | 历史保留和受控删除；资源摘要复核 |
| 任务版本 | 同任务/版本唯一、定义字段不许原地改写 | 依赖 DAG、能力覆盖、合法状态转换、租约 fencing |
| 候选聚合 | candidate_tasks 多对多，关联同 Operation 内的任务版本 | 候选实际包含全部必需产物和有效检查 |
| 调用回执 | 调用幂等键唯一，成功必须有回执/结果 | 同键不同参数冲突、unknown 恢复、外部副作用核对 |
| 预算 | 预留/结算触发器维护账户，超限预留回滚 | 参数预估、供应商价格来源、unknown 停止与重试策略 |
| 锁/空间读 | 锁字段结构、正包络、依赖归属 | JSON Pointer/区域语义、空间负查询和锁范围包含检查 |
| 持久事件 | Operation 内 sequence 唯一且事件不可更新 | 分配连续游标与领域状态同事务写入 |

SQL 的 STRICT 语法最低要求 SQLite 3.37；正式部署采用 16 章更高的 SQLite ≥3.45 基线，并探测 JSON/FTS5/RTree。默认忙等待 5000 ms，查询/接受失败走显式诊断，不无限锁等待。

`operations` 表仅表示产生世界修订的写操作。连接探测独立使用 `connection_probes`（ProbeRun），有自己的调用/Token预算、状态和结果引用，无 World/base/revision 外键；成功探测要求结果引用但不要求产生修订。

SQL 中 `*_hash`、`*_ref` 是绑定内容的逻辑引用；实际资源闭包继续由 ArtifactStore/现有资源表校验。本示例未复制完整 WIR 资源表、R-tree、导出和知识索引。`STRICT` 只约束 SQL 列类型，不能证明 JSON、几何或摘要有效。建连接后必须显式 `PRAGMA foreign_keys=ON`，否则 FK 声明不会成为执行保障。

接受事务的具体顺序为：事务外发布不可变资源和验证摘要 → writer `BEGIN IMMEDIATE` → 查 Operation 状态/epoch、世界 head/generation、锁 generation、候选内容/验证摘要、任务版本及空间依赖 → 插入不可变修订与对象引用 → 更新候选、Operation 结果和审计事件 → CAS 更新 head → 检查 rowcount 恰为 1 → COMMIT。任一步失败全部回滚引用，资源孤儿由后续 GC 处理。

```sql
UPDATE worlds
SET head_revision_id = :new_revision,
    head_generation = head_generation + 1
WHERE world_id = :world
  AND head_revision_id = :expected_head
  AND head_generation = :expected_generation;
```

CAS 语句不是完整接受实现：操作取消、锁和空间约束仍由同一事务中的此前查询判定。更新返回 0 行必须抛冲突并回滚，不能继续将候选标为 accepted。`revision.accepted` 事件与上述写入同事务；通知丢失时按游标补拉。

预算示例把本地批准额度与观察到的供应商消耗分开：unknown 保留 held_units；超额上游 usage 记录 observed_units/overrun_units，停止后续调用，不因账户 CHECK 限制而丢弃实际超支记录。调用完成后原子更新 reservation，触发器调整账户；业务代码不能绕过 reservation 直接改账户汇总。

旧 WIR 的 `parent_revision_ids` 是数组；新运行时首版单父链映射为 `[]` 或 `[parent_revision_id]`。SQL 中单父字段不授权改写旧包 Schema。撤销/重做复用已有快照，新修订以当前 head 为父并记录 restored_from，generation 递增，不调用模型。

## 6. Worker 启动、RPC 与取消

推荐通过 `asyncio.create_subprocess_exec()` 启动固定 worker 可执行入口，不经 shell。开发态入口为 `python -m world_builder.tools.workers.entrypoint`；Windows 冻结发行明确使用独立 `--console` worker 可执行文件，由 GUI 父进程使用隐藏窗口标志启动并重定向 stdin/stdout/stderr；GUI 自身以 `--windowed` 构建，不能复用其可能为 None 的标准流承载 RPC。Uvicorn 日志使用文件 handler，不依赖 GUI 控制台。若使用 multiprocessing spawn，则入口必须 `multiprocessing.freeze_support()`，严禁冻结程序的子进程重复创建窗口或调度器。

起始配置为一个 Uvicorn 服务 worker、两个工具 worker；Operation 截止 900 s、模型调用 24 次、工具调用 64 次、token 上限 120000，具体值统一读取 [runtime.design.toml](implementation/runtime.design.toml)，不得在各模块复制常量。它们是待测默认值，用户显式预算可更严格。

stdio 是本地内置工具协议，不冒充 MCP。每条 UTF-8 JSON 以 LF 结束，嵌入换行由 JSON 转义；建议单帧上限 1 MiB、有限队列背压，超限在完整分配前拒绝。大几何和图像通过 ArtifactRef 传递。stdin 为命令，stdout 只发协议帧，stderr 为有大小上限的脱敏日志，父进程同时排空两路以避免阻塞。

```json
{
  "rpc_version": "design-2026-11-12",
  "message_id": "msg_01",
  "kind": "execute",
  "call_id": "call_01",
  "task_id": "task_01",
  "task_version": 1,
  "lease_token": 7,
  "cancel_epoch": 0,
  "tool_name": "geometry.build_parts",
  "tool_version": "draft-1",
  "arguments_ref": "artifact_args_01",
  "grant_ref": "grant_01",
  "deadline_at": "2026-11-12T12:01:00Z"
}
```

响应类型为 `accepted/progress/result/error/cancel_ack`，包含 message_id、call_id、租约和取消代数；progress 不代表 ToolResult 成功。父进程只接受当前租约的最终结果，在恢复时持久化 unknown，再依据回执查询/幂等条件重试。RPC message_id 用于传输关联，不能代替逻辑 call_id。

取消先持久化再发 cancel 帧；工具在明确检查点停止，超过宽限期终止进程，并隔离已写暂存资源。Windows 受控 worker 使用 Job Object 追踪子进程树，POSIX 使用受控进程组；不杀用户原本独立启动的编辑器。结束 worker 不证明远程工具没执行。计算超限的资源终止也返回结构化失败，不当作普通网络重试。

## 7. Provider 与 MCP 的可实施分层

Provider 采用一个复用的 `httpx.AsyncClient`，每个请求显式配置连接/读/写/池等待超时、并发 semaphore、响应字节上限及 Operation 剩余期限。保留当前 urllib 路径禁止重定向的约束：`follow_redirects=False`；默认 `trust_env=False`，代理仅来自显式连接设置，不能意外继承环境把密钥送往未知代理。

`native_tools` 和 `action_json` 只负责 wire 编码/响应解码，输出统一 ModelTurn；字段关联、拒绝、截断、非法 JSON 和 usage 缺失分别归一。网络重试交给持久 runtime，适配器和 SDK 不再各自叠加重试。一个逻辑请求的多次传输尝试记录 attempt 和不确定费用，不能靠异常捕获悄悄再付费调用。

MCP 使用 16 章锁定的官方 SDK 及协议版本。推荐的 2026-07-28 连接执行该版本的发现与请求元数据机制，不能套用旧 `initialize` 生命周期。连接 startup probe 校验协议版本、服务身份、工具分页/Schema 与取消能力后才注册白名单。若另外兼容 2025-11-25，必须独立适配器和互操作测试，不在单连接上混合两套握手。

SDK 的内部 HTTP 传输与 Provider 的 HTTPX 客户端分开管理。当前依赖候选中的 MCP SDK 2.3.0 使用其 httpx2 依赖，Provider 使用 httpx 0.28.1；两者的 Client 类型、代理配置、异常类型和生命周期不能互换。统一包装为项目自己的 TransportFailure/ToolFailure，具体 SDK 异常只留脱敏调试记录。

MCPConnector 只负责连接、发现、调用和取消；ToolMapper 将外部工具映射为本地 ToolSpec；Gateway 再检查授权、参数、预算、回执和结果。服务器返回的新工具不自动进入现有任务工具集，正在运行的任务绑定原工具版本或显式失效。

## 8. 前端代码与数据流

React 管理界面组件和命令状态；Three.js 渲染独立于 React 组件树。`viewer/scene.ts` 持有一个 renderer、scene、camera 及资源缓存，通过稳定 source_id 建立 `Map<objectId, SceneHandle>`。几何/纹理按内容摘要复用，卸载通过引用计数 dispose，防止历史切换泄漏 GPU 资源。

工作台状态分三类：服务端事实（Operation/Revision/Candidate，仅从 API 读取）、编辑意图（未提交表单/选择/相机）、资源缓存（以 revision/hash/profile 分键）。UI 对 command 使用幂等键，不能乐观地把候选改成正式修订；收到 revision.accepted 或查询到接受回执后才更新世界头。

事件轮询持久 after 游标，处理重复和重新同步；视图用 AbortController 取消过期对象请求。模型日志、知识片段和工具结果不能通过 `dangerouslySetInnerHTML` 直接渲染。拾取结果由 GPU/CPU 代理映射回 source_id，再向 API 查询不可变 revision 的对象详情，不能把 mesh 数组下标当身份。

M2 将 Three.js 作为现有 ES Module 工作台可加载的预览模块；M3 再迁移完整 React 页面。构建资产全部随发行包离线分发，生产宿主不运行 Vite dev server。开发时 Vite 只代理明确 loopback API，生产静态文件与 API 同源，由本地服务提供令牌和来源校验。

## 9. 错误处理与可观测性落点

| 失败来源 | 内部错误与处理点 | 对外行为 |
|---|---|---|
| Pydantic / Schema | api 层收集字段路径，去掉敏感值 | 400 或 422；稳定 request_id |
| sqlite3.IntegrityError | Repository 转领域约束冲突 | 409/422；不返回原始 SQL 或文件路径 |
| CAS rowcount = 0 | CommitService 的 STALE_BASE | 409，世界头不变，候选标 stale |
| 锁/作用域 | Gateway 或 CommitService 的 SCOPE_DENIED/LOCKED | 403；不重试放宽权限 |
| Provider 超时/断线 | Adapter→Runtime 的 unknown outcome | 持久账本和保守预算，不伪装零费用 |
| worker 异常/被终止 | Supervisor→Gateway 的 worker_lost | 查回执、隔离产物、有限恢复 |
| MCP 协议不符 | Connector 的 incompatible_protocol | 连接不可用；不隐式切换握手 |

日志字段采用 `request_id, operation_id, task_id, task_version, call_id, candidate_id, revision_id, event_type, duration_ms`；禁止记录密钥及模型私有推理。UI 进度从持久事件读取，性能日志不成为权限事实。候选接受、取消、恢复、锁变更、预算调整必须有审计事件；普通渲染帧无需逐帧持久化。

## 10. CI、打包与实施顺序

| 阶段 | 具体检查/交付 | 失败时阻断 |
|---|---|---|
| 048 契约/存储 | JSON Schema 正反例、DTO 严格性、SQL 副本迁移、FK/幂等/空间依赖/崩溃注入、旧包读取 | 新协议联调与正式数据迁移 |
| 049 异步运行时 | 两适配器同义行动、预算竞争、取消/迟到、真实只读 MCP、HTTP Host/Origin/token 负例 | M1 真实模型批次 |
| 050 单栋 | 受控 worker 输入/输出、独立日志、未知回执、两协议诊断修正、源包重开 | 宣称单栋闭环成功 |
| 051 场景/预览 | 固定资产与检索集、Three.js 拾取/释放、同修订双目标、坐标基准和实际加载 | 宣称完整小场景可用 |
| 052 工作台 | TypeScript strict、组件测试、Playwright 用户流程、稳定对象修改/历史与锁 | 宣称完整修改闭环 |
| 发行 | `pip`/npm 锁依赖、SBOM、离线资源清单、Windows 原生 PyInstaller 构建、干净机器启动/关闭 | 发布便携包 |

Python 单元/集成用 pytest，类型检查覆盖端口和 DTO，前端用 TypeScript/Vitest/Playwright。依赖版本解析成功不等于功能兼容；安装 smoke、真实模型和引擎验收分别保留。Windows 发行包应在 Windows 构建，macOS 开发环境不能宣称已完成 Windows 打包。

启动与健康检查要覆盖：`bootstrap --worker` 早分流、应用数据根不是 SMB、单协调者锁、持久化配置解析、DB 版本/资源检查、API ready、桌面窗口、按需 worker/MCP。关闭测试确保没有本应用拥有的 worker 残留；不新增开机自启或后台守护服务。

## 11. 本次 SQL 设计验证与边界

2026-11-12 使用 Python 3.12 自带 SQLite 3.54.1，在 `:memory:` 执行本章 SQL 建表成功；18 项检查通过，包括：候选关联多个任务、跨 Operation/世界引用拒绝、generation 回退拒绝、不可变修订/任务定义、未验候选不得 accepted、非法任务状态、调用幂等键冲突、成功回执要求、unknown 预算保持预留、超限预留拒绝、上游观察超额保留、事件游标重复、非法空间包络和字段锁。`foreign_key_check` 无错误，`integrity_check` 为 ok。

该结果仅验证 SQL 草案的结构及上述约束，不证明生产 Repository 的迁移、领域状态机、CAS 并发、资源完整性或恢复已经实现。048 应将本草案映射为现有 schema 的可回退迁移，保留原库副本，不能把空库建表 SQL 作为原地升级脚本。

## 12. 技术依据

本轮于 2026-11-12 核对现有 [Repository](../src/world_builder/storage/repository.py)、[运行时](../src/world_builder/agents/runtime.py)、[桌面宿主](../src/world_builder/desktop/app.py)及 [Canvas 预览](../web/features/preview.js)。上述文件支持“现有实现”的描述，新增端口、线程结构、worker RPC 和目标目录属于本次推荐设计。

同日查阅 [Python sqlite3](https://docs.python.org/3.12/library/sqlite3.html)与 [SQLite 外键](https://www.sqlite.org/foreignkeys.html)，用于连接归属、显式外键及复合引用设计；查阅 [asyncio subprocess](https://docs.python.org/3.12/library/asyncio-subprocess.html)，用于受控子进程和管道管理。冻结应用的子进程入口参考 [PyInstaller multiprocessing 说明](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#multi-processing)，GUI 主线程约束参考 [pywebview FAQ](https://pywebview.flowrl.com/guide/faq.html)。这些资料不代替本项目的 Windows 集成测试。
