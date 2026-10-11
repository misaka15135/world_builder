# API Agents JSON 契约 0.1.0

适用范围（2026-10-10）：当前本地 main 的固定 A—F 实现。本文与对应 Schema/运行 skills 继续按 0.1.0 使用；[029](../../work_order/029_scene_task_contracts.md) 将定义通用场景任务和兼容策略，尚未替换本契约。产品目标及当前限制见 [项目基线](../00_project_baseline.md)。

适用于 [023](../../work_order/023_api_agent_pipeline.md)。实现入口：[contracts.py](../../src/world_builder/agents/contracts.py)、[validation.py](../../src/world_builder/agents/validation.py)、[runtime.py](../../src/world_builder/agents/runtime.py)。

## 权威边界

所有 API 响应都是候选数据。本地 Schema、语义检查、预算、依赖失效、几何编译和存储为权威。模型没有 shell、文件写入、网络二次请求、代码执行或修改校验策略的工具。更换供应商只改变 provider。

世界采用右手坐标：X 东、Y 北、Z 上，长度 m，角度 rad。本版没有旋转参数，几何统一整米轴对齐盒体，bounds 为 `min` 包含、`max` 不包含。B/D 使用世界绝对坐标，E 使用 site.bounds.min 为原点的局部坐标。编译只做坐标平移，不改变 E 布局。

region_m 由调用方指定，支持 32..512、16 的整数倍；seed 为 uint64。相同 seed 不保证远端模型响应相同，字节回放才能保证派生产物相同。

## 请求与响应

请求包括 contract_version、stage、scope_id、request_id、prompt、seed、region_m、units、axes、geometry、limits、attempt、revision_round、dependencies、feedback、instructions 和 response_schema。顶层禁止额外字段，详见 [请求 Schema](../../schemas/agent-request-0.1.0.schema.json)。

dependencies 是带 stage、规范化数据 SHA-256 和 data 的数组。E 为 site ID 到完整设计的映射。每个任务只收到已接受的依赖快照。request_id 是绑定 prompt、依赖、skill、Schema、轮数、尝试与本地预算的 SHA-256；先计算不含 request_id、尚未绑定常量的基础请求，再把该 ID 固定到响应 Schema。这样避免循环哈希。

响应 envelope 必须精确包含：

```json
{
  "contract_version": "0.1.0",
  "stage": "E",
  "request_id": "sha256:由请求提供的64位十六进制摘要",
  "scope_id": "shop_01",
  "payload": {}
}
```

上例仅展示 envelope 形状；实际 payload 必须满足相应阶段 Schema，示例摘要不是合法值。所有阶段禁止未知字段，不能返回代码块。重复键、非有限数字、超大响应会被拒绝。数学上为整数的 JSON 数字如 `1.0`/`1e0` 规范化为整数；不会填补字段或修补 JSON。响应 Schema 绑定当前 stage/request_id/scope_id，不能串用另一栋建筑的响应。

## 阶段字段与本地验收

| 阶段 | payload 核心内容 | 本地验收 |
|---|---|---|
| A | title、region_m、style、requirements、acceptance_criteria | 区域保持调用方值；唯一需求 ID；数量范围合法；场地预算 |
| B | cell_m、heights、ground_material、water、rationale | 网格完整覆盖区域；整数高程 1..24；水在地面上方、区域内且互不重叠 |
| C | types：requirement_id、count、programme、size_m、max_height_m、design_brief | 唯一类型 ID；每项对应 A；总数量逐项满足 A 的上下限 |
| D | districts、sites、roads | 地区/场地不交叠；引用正确；恰好满足 C 数量；包络、干燥地面、地基和道路连接 |
| E | site_id、concept、parts、spaces、entry_cell、routes | 只能修改指定场地；构件无重叠且在包络内；空间净空、道路入口、逐格支撑及每层通路 |
| F | verdict、accepted_sites、requirement_review、fixes、limitations | accept 必须覆盖所有场地/需求、无返工；revise 必须有合法作用域 |

B 的 heights 是 **单元高度**，不是顶点高度。若 region_m=32、cell_m=8，数组恰为 4×4；每个单元填充 z=0..height。高程、河床与水位均由模型声明；程序不模拟排水。

C 的 size_m 是场地宽度/进深上限，D 可选择更小场地（至少 4×4 m）；max_height_m 是 D/E 的上限。A 需求未映射到 C 或 C 数量未映射到 D 均失败。模型对用户原文的语义忠实度由 F 审查，机器无法证明开放语言需求被完全理解。

在此固定流水线中，A 的每个 `requirement` 是一个将由 C 分类、D 放置的**场地类型需求**，不是对原句逐词拆分。道路、地形、入口、房间和楼梯应写入相应场地的描述与整场景验收条件，不各自占用 `max_sites`。A 的 `min_count` 总和仍不得超过 `max_sites`；超限用 `brief.site_budget` 作为可反馈的模型提案错误，在阶段尝试预算内允许重提，但绝不提高调用方上限。独立要求的另一栋建筑不可因预算而被悄悄合并。

D 的场地不能相互覆盖或进入水体，底标高须不低于所有下方地形单元。有高差时必须明确 foundation=true；编译器仅填充 site 下方至该基准面的差值。道路为一米厚矩形，宽度至少两米；道路须贴地，桥可悬跨，桥面不能进入水体。道路/桥在相同顶标高沿至少一米边相接，网络至少含一条贴地道路。每个 site 接路，路顶等于 site 基准面+1。

E 的 parts 含 ID、角色、bounds、material。角色限基础、楼板、墙、屋顶、楼梯、窗、柱、家具、景观；materials 的准确目标映射在 compiler.py。构件可相接，不能体积重叠。门窗空隙须由模型分拆墙体留下；没有隐式开洞或模板补全。spaces 是不含固体的可用空间，家具应放在这些净空范围之外。空间应有至少两米净高。

entry_cell 和 routes.cells 指一格宽、两格高的站立空气格左下角。每点须有脚下支撑，逐点相邻（水平曼哈顿距离=1、高差绝对值≤1），阶梯上方有额外净空检查。每条 route 从 entry_cell 到指定 space.access_cell，每个空间恰有一条路径；有室内需求时，每一处 floor 顶标高均需被路径访问。验证物理格位而非仅信任模型声明的连通图。整格上升属于需要跳跃的近似，不等于无障碍或引擎实走。

F 的返工阶段仅 B/C/D/E。B/C/D 的 scope_id 为 scene；E 必须引用现有 site。A 不能由 F 偷改需求以接受较差结果。无法满足的要求须明确导致返工耗尽，后续由用户调整输入或扩展契约。

## 状态、错误与证据

运行日志事件包括 started、request、accepted、rejected、invalidated、revision_requested、planning_completed、failed。planning_completed 只说明计划通过；result.json 才记录编译/归档/导出结果。失败的 feasibility 为 unknown；重试耗尽不证明数学无解。

错误码按作用域分类：json、contract、request、brief、terrain、catalogue、siting、design、review、budget、api、replay、execution。请求失败、模型截断、非法引用和空间失败保留证据；不伪造目标测试。模型/API 输出不能创建文件路径，所有文件名由本地 ID/摘要生成。

本地配置 Schema 为 [agent-config](../../schemas/agent-config-0.1.0.schema.json)。Schema 由同一代码定义生成，更新后执行：

可选的 `deepseek_thinking` 仅用于 DeepSeek 官方 Chat endpoint，值为 `enabled` 或 `disabled`；它只改变供应商请求体，不改变 A—F 计划 Schema。省略时不传该字段，由供应商采用默认值。不同设置的真实评估必须分开登记，不可混合分母。

```powershell
$env:PYTHONPATH = 'src'
python tools/write_agent_contracts.py
python tools/write_agent_contracts.py --check
python -m pytest tests/test_agent_pipeline.py -q
```

不兼容字段、坐标、原语或语义变化必须升级版本；已存请求/响应及 WIR 产物不原地覆盖。硬规则修改应同时更新此文档、skills 和负例测试。
