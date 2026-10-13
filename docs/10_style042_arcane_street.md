# 042 首个详细魔法街区：查看与证据

日期：2026-10-13。当前产物是 64m×64m 小街区，包含两栋住宅、两栋两层商铺、一座喷泉广场，以及窗框、木构门廊、家具和楼梯。真实 API 决定布局和建筑参数，本地详细构建器执行；[契约与边界](contracts/style042-v0.1.1.md)。

## 查看

Windows 双击 [Unity 启动文件](../tools/open_style042_unity.cmd)。它打开独立 `adapters/unity/style042_project/`，进入 `Assets/Generated/API/ArcaneAPI.unity`。编辑器路径优先使用第一个参数或 `UNITY_EDITOR` 环境变量，未指定时使用本机 `D:\Unity\6000.3.24f1\Editor\Unity.exe`。其他电脑可在 Unity Hub 添加该项目文件夹，使用 6000.3.24f1 打开相同场景。Git 分支精选保留了实际场景、GLB、材质、meta 与路径数据，查看已有产物不需要 API 密钥，也不需要先运行 Python 生成工具；首次打开需要 Unity 解析项目包依赖。

Scene 视图可旋转查看；Play 后是自由相机：WASD 移动、Q/E 升降、按住鼠标右键转向、Shift 加速。自由相机没有实体碰撞，实走证据由另外的自动 CharacterController 测试取得。普通查看选 `ArcaneAPI.unity`；`ArcaneWalkValidation.unity` 用于自动检查，交互编辑器内完成后仅退出 Play，批处理检查才退出测试进程。

真实产物位于 `artifacts/style042/arcane-v3/`：`scene.worldpkg`、`repository/scene.world.json`、`unity/scene.glb`、调用记录和 `unity-evidence/`。固定本地对照在 `artifacts/style042/baseline-v3/`；它利用旧详细构建能力搭建同范围小街区，未声称是旧全城的逐字复制。用户原 sample_project 的场景和修改保持原样。

Git 发布只保留 [精选交付快照](../examples/style042_delivery/README.md)：自包含 worldpkg、接受的模型参数、原登记代码哈希、关键结果和六张对照图。完整调用记录及失败日志仍仅在上述本地 artifacts 中。快照可用于查看/核对，但不含重做原始 API 请求回放所需的原始调用目录；现有回放通过结果与重新执行回放是两回事。

## 已有机器证据

真实布局/建筑参数来自 v2 的六次 API 响应；v3 补了两次 F 审查调用，接受后生成 646 个网格。v1 的三次布局失败、v2 的源采样失败保留，v3 是续跑结果。一次无网络回放的世界包、GLB 和源几何字节一致。本地对照为 555 个网格。

Unity 6000.3.24f1 实际导入 API 646 个网格、核对 646 个 bounds，建立 642 个非水体碰撞体；本地对照为 555 个网格与 551 个碰撞体。源端 16 个房间路线通过，目标 Play Mode 角色连续走通 16/16 间房（包括两层商铺），12,605 帧运动、9,329 接地帧；两次测试路径失败保留。目标路径采用完整楼梯中心线，随后在有脚下支撑的上层平面寻路，避免把源端胶囊接触边缘的预测高程当作每一帧必须达到的角色高度。详见 `unity-evidence/walk_validation.json` 与 [042 工单](../work_order/042_api_legacy_scene_visual_parity.md)。

两组截图使用相同渲染设置和相机，分别在两份产物的 `unity-evidence/{overview,street,detail}.png`。人工观感尚需用户确认；颜色材质、阶梯屋顶与简单树木仍明显，当前不代表整个魔法城邦或其他三个场景已完成。

## 开发复核

以下准备/回放命令需要本地完整 `artifacts/style042/`，不是 Git 克隆后查看现有 Unity 场景的前置步骤。

```powershell
python tools/run_style_042.py --batch v3 --check
python tools/prepare_style_042_unity.py
```

已有登记输出不可重跑覆盖。原始 v3 的纯离线回放已执行，查看 `replay_validation.json` 即可；再次回放应选择独立新输出目录并维持原请求/代码哈希。Unity 构建与重开入口分别为 `WorldBuilder042Builder.Build` / `Reopen`，实走入口为 `VerifyWalk`；批处理通过 `WB042_CASE=API|Baseline` 和 `WB042_EVIDENCE` 指定案例与证据目录。
