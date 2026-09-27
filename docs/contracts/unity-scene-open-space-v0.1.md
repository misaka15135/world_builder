# Unity 场景开放空间样件 0.1

本样件从场景流水线生成的 WIR 选取一个 `kind: open_space` / `ground_plan` 实体，将铺装、步道和固定设施导出为 GLB 盒网格。它用于验证新场景修订可进入 Unity 6000.3.24f1，并保留源 ID；不是完整城邦导出。源修订为 `revision_6e0278367b0b90212b809b`，世界 ID 为 `world_fc3383ea0483264d`，样件实体为 `open_space_site_001`。

在仓库根目录运行：

```powershell
$env:PYTHONPATH='src'
python tools/export_unity_open_space.py --source artifacts/scene-arcane-open-space-current/wir.json --source-id open_space_site_001 --output artifacts/unity-scene-open-space-plaza-new
```

输出格式 `unity-glb-scene-open-space-0.1`，适配器 `0.1.0-scene-open-space.1`。单位为米；WIR 坐标 `(东, 北, 上)` 经 GLB 轴变换后，Unity 坐标为 `(X 东, Y 上, Z 北)`。34 个构件分别为铺装、步道和 32 个灯、长椅等设施；GLB 节点及 Unity `WorldBuilderSourceId` 保留源 ID。材料是石材、浅色步道、半透明灯和木设施的近似色；几何为平坦长方体，设施高度受源场址包络限制。未导出地形、河道、建筑、全城道路、原生 Terrain 或 NavMesh；未验证玩家漫游。GLB 清单的 `target_load=not_run` 是离线默认状态，实际目标结果另见验证 JSON。

目标项目 `adapters/unity/sample_project/Assets/WorldBuilderOpenSpace/` 已放入该 GLB、清单与 Editor 构建器。`WorldBuilderOpenSpaceBuilder.Build` 导入 GLB，给每个构件挂源 ID 与 MeshCollider，验证铺装尺寸、Y 轴及步道位置，保存 `OpenSpacePlaza.unity`。`WorldBuilderOpenSpaceBuilder.ValidateSaved` 在另一个编辑器进程中重新打开场景，复核 34/34 源 ID 与碰撞体。两个 Unity 6000.3.24f1 批处理进程均正常退出；结果分别在 `artifacts/unity-scene-open-space-plaza/target-validation.json` 和 `target-reopen-validation.json`，均为 `target_load=pass`、`collision=pass`、34/34 构件。`tests/test_unity_scene.py` 独立解析 GLB 及源 WIR，检查修订、节点 ID、几何和哈希。下一步需把完整场景的其余实体接入 Unity、生成对象级损失报告，并进行图形与运行时验收。
