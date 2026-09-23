# World Builder

自然语言驱动的分层三维世界生成与编辑系统。

当前阶段：M2 最小生成闭环实施中。已提供 128 m 小范围本地生成试验：固定 seed、五阶段提交、6 栋建筑/2 栋室内模板、源端校验、SQLite 存档和故障恢复；v2 增加最多 3 次候选的楼梯修复、建筑预留空间反馈、锁冲突保护和逐次日志。完整城邦、模型接入、查看器及目标导出尚未完成。能力与限制见 [006 运行说明](docs/contracts/generation-v0.1.md)。

## 方案文档

1. [问题重述与需求基线](docs/01_problem_restatement.md)
2. [可行性研究与技术证据](docs/02_feasibility.md)
3. [正式技术方案](docs/03_formal_proposal.md)

首版方向已确认：个人或小团队、普通电脑、本地查看与编辑、允许云端模型 API，优先魔法城邦及 Unity/Minecraft 输出。

建议架构为语言模型规划、程序化生成、约束验证、世界中间表示 WIR 和目标适配器。建筑工程输出单独分阶段验证。

## 协作入口

每次工作前先读 [AGENTS.md](AGENTS.md)、[工单索引](work_order/README.md)、[总规划](work_order/000_project_master_plan.md) 和当前工单。完成动作应即时记录，完成事项同时勾选与划线。

当前任务是 [006：最小分层生成闭环](work_order/006_generation_vertical_slice.md)。当前在 Windows 基准主机本机运行，使用 PowerShell：

```powershell
$env:PYTHONPATH = 'src'
python tools/generate_world.py --output artifacts/my-pilot --seed 101
$testRunDir = Join-Path (Get-Location) ('artifacts/pytest-006-' + [guid]::NewGuid().ToString('N'))
python -m pytest -q --basetemp $testRunDir
python tools/check_project_docs.py
```

运行需要 Python 3.10+ 和 `jsonschema`，测试另需 `pytest`。当前实测依赖与原锁定文件存在版本差异，见 [基准记录](docs/contracts/environment-baseline.md)；没有修改全局依赖。重复相同生成命令可继续未完成阶段，完整执行后不重复生成。输出的 JSON 快照附带同目录资源，并非正式 `.worldpkg` 或目标平台场景。
