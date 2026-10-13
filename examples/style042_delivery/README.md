# 042 首例精选交付快照

日期：2026-10-13。该目录保存已有产物的精选副本，不执行新 API 调用。`API/` 为真实 DeepSeek v3 续跑的 64m 魔法街区；`Baseline/` 为同范围固定本地对照。模型决定布局和建筑参数，本地确定性构建器生成细几何。不是完整魔法城邦，也不是四场景全部交付。

## 直接查看

在 Unity Hub 添加 `adapters/unity/style042_project`，使用 Unity 6000.3.24f1，打开 `Assets/Generated/API/ArcaneAPI.unity`；对照为 `Assets/Generated/Baseline/ArcaneBaseline.unity`。场景/GLB/材质/meta 已随分支保留，无需密钥。操作及验证边界见 [查看说明](../../docs/10_style042_arcane_street.md)。

| 对照 | 本地固定基线 | 真实 API |
|---|---|---|
| 俯瞰 | [overview](Baseline/overview.png) | [overview](API/overview.png) |
| 街面 | [street](Baseline/street.png) | [street](API/street.png) |
| 近景 | [detail](Baseline/detail.png) | [detail](API/detail.png) |

## 保留与排除

每个案例保留 `accepted.json`、自包含 `scene.worldpkg`、源结果和 Unity 加载/重开报告、三张同设置截图。API 还保留原登记上下文（含原始代码哈希）、`delivery_summary.json`、历史精确回放结果及角色实走报告。646 个 API 网格、642 个非水体碰撞体、16/16 房间路线已在原目标环境通过；人工观感待复核。

没有上传密钥、环境变量、请求头、原始请求/响应目录、SQLite 工作库、Library 缓存、编辑器日志和重复失败导出。完整实验记录仍在本地 `artifacts/style042/`。API 快照为 v2 六次响应复用、v3 两次新审查请求的续跑结果，不是独立可靠性样本。记录的精确回放已经通过；此精选快照不包含再次执行原请求回放所需的全部记录。

接受的模型概念文本可能误称建筑所在街道一侧或材料；明确参数、实际源几何及 Unity 验证是事实依据，不把概念叙述或 F 的 accept 当作观感通过。

进一步开发与四场景扩展见 [042 工单](../../work_order/042_api_legacy_scene_visual_parity.md)，本次筛选发布见 [044 工单](../../work_order/044_deepseek_branch_publication.md)。
