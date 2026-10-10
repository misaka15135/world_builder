# World Builder

2026-10-10 本地分支职责：`main` 为 Agent 主导的场景搭建产品主线，由原 `codex/api-agent-pipeline` 重命名；`codex/local-validation` 保留原 `main` 的规则生成、目标验证和回归对照。产品范围为场景搭建，不包含游戏玩法逻辑生成。远端分支尚未同步，两条本地分支暂未配置 upstream。调整记录见 [027 工单](work_order/027_branch_role_alignment.md)。

## Windows 桌面应用

双击 `dist/WorldBuilder/WorldBuilder.exe` 打开独立应用窗口。便携包为 `dist/WorldBuilder-0.1.0-win-x64.zip`，需完整解压并保留 `_internal`。无需安装 Python；本机已具备所需 WebView2 运行库。

可测试离线样例、自己的 API、A—F 进度、几何预览、历史回放与产物下载。历史和非密钥设置保存在 `%LOCALAPPDATA%/WorldBuilder`，更新应用目录时保留。详见 [桌面版使用与构建说明](docs/07_desktop_application.md)。

## 本地应用与网页测试台

双击 [start_workbench.cmd](start_workbench.cmd)，或运行 `python tools/run_workbench.py --open`，打开 `http://127.0.0.1:8765`。

支持场景输入、API 配置、离线样例、历史回放、A—F 进度、可旋转/剖切的源几何预览、JSON 诊断与产物下载。网页功能模块通过 HTTP API v1 接入独立任务服务，无需前端构建工具或 CDN。运行历史保存在本地忽略目录，填写的密钥仅用于单次运行。

详见 [测试台使用与模块扩展说明](docs/06_web_workbench.md)。当前是只读预览与测试应用；完整世界编辑及真实目标效果另行验收。

## 当前分支：API 驱动 A—F 多智能体

`main` 的默认产品入口为 `generate-world` / `tools/generate_agent_world.py`。
A 场景需求 → B 地形与 C 风物清单并发 → D 空间分配 → 每个场地独立 E 设计 → F 审查与有限返工。
各阶段均由配置的 API 提交 JSON 计划；本地负责不可绕过的规则验证、几何编译、WIR 持久化与导出。
API 地址和模型使用 `yourapi` 占位。配置未完成时明确失败，不调用旧规则规划器代替模型。

详见 [运行与架构说明](docs/05_api_agent_pipeline.md)、[JSON 契约](docs/contracts/api-agents-v0.1.md) 和 [023 工单](work_order/023_api_agent_pipeline.md)。

无需密钥的**人工响应样例**（验证程序闭环，不代表模型质量）：

```powershell
$env:PYTHONPATH = 'src'
python tools/generate_agent_world.py --prompt '一条街旁的一栋两层木构商铺和一座公共大厅，都能进入，商铺上层可达。' --region-m 32 --fixtures examples/agent_scene.responses.json --output artifacts/agent-runs/example --minecraft --unity
```

初版能力：模型直接声明整米盒体构件、地形单元、空间与逐格通路；输出自包含 `.worldpkg`、Minecraft schematic 和 Unity 可导入 GLB。真实 API 质量、游戏内加载和漫游尚未验收。输出目录必须为新目录。

## 历史规则主线（保留作回归对照）

自然语言驱动的分层三维世界生成与编辑系统。

当前阶段：M2 最小生成闭环实施中。已提供 128 m 小范围本地生成试验：固定 seed、五阶段提交、6 栋建筑/2 栋室内模板、源端校验、SQLite 存档和故障恢复；v2 增加最多 3 次候选的楼梯修复、建筑预留空间反馈、锁冲突保护和逐次日志；v3 增加可替换的自然语言规格 JSON 接口、已接受响应回放与自包含 `.worldpkg` 交换。512 m、80 栋建筑/5 栋室内的独立离线源端规格在预登记基准中 30/30 完成。[Unity 两层建筑样件](docs/contracts/unity-sample-v0.1.md)已在目标编辑器由控制器连续穿门上楼；[Minecraft 区域样件](docs/contracts/minecraft-sample-v0.1.md)已在目标游戏由玩家连续走通南门至二层。真实模型服务、通用城邦跨目标导出和本地查看器尚未完成。能力与限制见 [006 运行说明](docs/contracts/generation-v0.1.md)。

## 方案文档

1. [问题重述与需求基线](docs/01_problem_restatement.md)
2. [可行性研究与技术证据](docs/02_feasibility.md)
3. [正式技术方案](docs/03_formal_proposal.md)

首版方向已确认：个人或小团队、普通电脑、本地查看与编辑、允许云端模型 API，优先魔法城邦及 Unity/Minecraft 输出。

建议架构为语言模型规划、程序化生成、约束验证、世界中间表示 WIR 和目标适配器。建筑工程输出单独分阶段验证。

## 协作入口

每次工作前先读 [AGENTS.md](AGENTS.md)、[工单索引](work_order/README.md)、[总规划](work_order/000_project_master_plan.md) 和当前工单。完成动作应即时记录，完成事项同时勾选与划线。

旧规则路径的入口是 [006：最小分层生成闭环](work_order/006_generation_vertical_slice.md)，以下命令保留作历史对照；安装后的别名为 `generate-rule-world`。在 Windows 基准主机本机运行，使用 PowerShell：

```powershell
$env:PYTHONPATH = 'src'
python tools/generate_world.py --output artifacts/my-pilot --seed 101
python tools/generate_world.py --city --output artifacts/my-city --seed 101 --timeout-ms 120000
python tools/generate_world.py --output artifacts/model-demo --seed 17 --prompt '一座河畔魔法小镇' --model-fixture examples/pilot_model_response.json
$testRunDir = Join-Path (Get-Location) ('artifacts/pytest-006-' + [guid]::NewGuid().ToString('N'))
python -m pytest -q --basetemp $testRunDir
python tools/check_project_docs.py
```

运行需要 Python 3.10+ 和 `jsonschema`，测试另需 `pytest`。当前实测依赖与原锁定文件存在版本差异，见 [基准记录](docs/contracts/environment-baseline.md)；没有修改全局依赖。重复相同生成命令可继续未完成阶段，完整执行后不重复生成。输出的 JSON 快照附带同目录资源；`tools/worldpkg.py` 可将自包含修订导出、校验并导入 ZIP64 世界包。它不是 Unity 或 Minecraft 场景。
