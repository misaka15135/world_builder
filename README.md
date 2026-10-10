# World Builder

面向自建游戏地图的玩家和创作者，建立 **Agent 主导的场景搭建系统**：从创作描述产生分阶段计划，经过本地校验与几何编译，保存为独立于目标平台的 WIR 源世界，再导出到游戏或引擎。目标覆盖自然、建筑和混合场景，降低场景制作的时间与技能门槛。当前范围不包括游戏玩法逻辑或自动线上投稿。

项目定位与实施边界见 [当前项目基线](docs/00_project_baseline.md)，文档用途见 [文档索引](docs/README.md)。

## 当前可运行原型

当前版本 0.1.0 使用固定流程：A 需求 → B 地形与 C 风物清单并发 → D 选址 → 每个场地独立 E 设计 → F 整场景审查与有限返工。API 模型提交结构化计划，本地程序执行严格校验、几何编译、WIR 存档与导出；配置缺失时明确失败，不回退旧规则规划器。

| 能力 | 当前边界 |
|---|---|
| 场景生成 | 轴对齐整米盒体、格状地形、静态水和有限材质；场地仍受建筑、支撑和道路连接约束 |
| 数据与导出 | 自包含 `.worldpkg`、Unity 静态 GLB、Minecraft Sponge v3 schematic 与映射/损失报告 |
| 本地应用 | 网页测试台、Windows 桌面壳、只读旋转/剖切/拾取、阶段记录、历史回放和下载 |
| 现有证据 | 人工响应样例验证程序闭环；真实 API 质量、成本及其生成场景在目标中的加载/通行仍待 024 验收 |
| 后续规划 | 按能力调度、自然资产、稳定修订、用户反馈修改与目标能力配置均尚未实现，见 029—037 |

GLB 输出不包含新增的自动 Unity 场景导入、碰撞体或 NavMesh；schematic 需要目标侧工具放置。当前文件导出不能证明场景在游戏中可用。旧规则路径的城堡、船只等功能及目标侧样件证据不自动代表 Agent 主线能力。

## 启动与验证

网页：双击 [start_workbench.cmd](start_workbench.cmd)，或在项目根目录运行：

```powershell
python tools/run_workbench.py --open
```

默认打开 `http://127.0.0.1:8765`，源码运行需 Python 3.10+ 和项目依赖 `jsonschema`。详见 [网页测试台](docs/06_web_workbench.md)。

Windows 桌面：本机构建产物为 `dist/WorldBuilder/WorldBuilder.exe`，便携包为 `dist/WorldBuilder-0.1.0-win-x64.zip`。完整解压并保留 `_internal`；无需另装 Python，系统需 WebView2 Runtime 和 .NET Framework 4.6.2+。历史与非密钥设置保存在 `%LOCALAPPDATA%/WorldBuilder`。打包产物不会随源码文档修改自动更新，详见 [桌面应用](docs/07_desktop_application.md)。

命令行默认产品入口为 `generate-world`（安装后的命令）或 [generate_agent_world.py](tools/generate_agent_world.py)。无需密钥的人工响应样例：

```powershell
$env:PYTHONPATH = 'src'
python tools/generate_agent_world.py --prompt '一条街旁的一栋两层木构商铺和一座公共大厅，都能进入，商铺上层可达。' --region-m 32 --fixtures examples/agent_scene.responses.json --output artifacts/agent-runs/example --minecraft --unity
```

每次输出目录必须不存在；已使用 `example` 时换一个新目录。样例响应由人工编写，不会根据改写的描述生成新场景。自己的 API 配置、预算与精确回放方式见 [Agent 运行说明](docs/05_api_agent_pipeline.md) 和 [JSON 契约](docs/contracts/api-agents-v0.1.md)；示例配置中的 `yourapi` 必须替换。

## 分支与协作入口

2026-10-10 的分支职责：`main` 为 Agent 产品主线，由原 `codex/api-agent-pipeline` 更名；`codex/local-validation` 保留原 `main` 的规则生成与本地验证对照。两条分支已推送并追踪对应 origin 分支，GitHub 默认分支为 main，旧 Agent 远端分支保留。调整见 [027](work_order/027_branch_role_alignment.md)，推送记录见 [040](work_order/040_remote_branch_publication.md)。旧规则路径的运行方式与证据见 [006 说明](docs/contracts/generation-v0.1.md)，不是当前产品默认入口。

每次工作先读 [AGENTS.md](AGENTS.md)、[工单索引](work_order/README.md)、[总规划](work_order/000_project_master_plan.md) 和当前工单。实施入口为 [029 通用场景契约](work_order/029_scene_task_contracts.md)；024 随能力推进积累真实效果证据，038 单独核对历史工单。IFC 是独立可选扩展。早期 01—04 方案保留作历史参考，当前目标与路线以项目基线和总规划的当前部分为准。
