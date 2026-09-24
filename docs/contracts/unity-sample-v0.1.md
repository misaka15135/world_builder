# Unity 两层建筑目标样件 0.1

本样件是 008 的手工两层建筑目标试验，不是任意 WIR 城邦导出器。输入固定为 `examples/two_storey_building.world.json` 的 `revision_two_storey_001`。源端只给出建筑、房间、楼梯的体积和关系，没有墙、门、踏步或完整家具几何，因此导出器明确采用样件级构造规则，并在对象级报告中记为 `approximated`。

## 版本与产物

2026-09-23 本机 `MISAKA` 使用 Unity `6000.3.24f1`。仓库中的 Unity 项目位于 `adapters/unity/sample_project/`，首次打开后 `Packages/manifest.json` 与锁文件实际固定 URP `17.3.0`、glTFast `6.20.0`。前者由目标编辑器将随附模板原有 `17.0.1` 升级至 `17.3.0`；后者来自 Unity 包注册表，最低编辑器版本为 `6000.0`。这些是样件的实际包版本，不沿用旧的 Unity `6000.3.0f1` 历史 profile。

`artifacts/unity-sample/v2/library.glb` 为 glTF 2.0 二进制，SHA-256 为 `f9dd083acf180287549b23d1aa70e1b0fab4eaa69a484ee4c58e425bb252f75a`；同目录包含 `manifest.json`、`target_profile.json` 和符合 WIR 0.1 记录结构的 `export_report.json`。导出器为 `src/world_builder/adapters/unity/sample.py`，命令入口为 `tools/export_unity_sample.py`。同一 GLB 与 manifest 复制到 Unity 项目的 `Assets/WorldBuilderSample/`，由 glTFast 作为原生 Prefab 导入；`WorldBuilderSampleBuilder` 建立场景、对象 ID 组件和 MeshCollider。`LibrarySample.unity` 是实际生成的场景文件。

## 坐标与几何

WIR 为右手系、米单位，坐标为 `(东, 北, 上)`。目标 Unity 场景约定 `(X 东, Y 上, Z 北)`，行主序 4×4 映射为 `[1,0,0,0; 0,0,1,0; 0,1,0,0; 0,0,0,1]`，行列式为负。glTF 文件自身为右手 Y-up；导出前使用 `(西, 上, 北)`，即 `[-1,0,0; 0,0,1; 0,1,0]`，其行列式为正。目标 glTFast `6.20.0` 在导入时反射 X 轴，构成最终的 Unity 映射。v1 曾按反射 Z 轴的假设输出，实际东窗出现在 `(-23.88,6,-13)`；v2 通过导入后东窗边界 `[23.75,5,12]` 至 `[24,7,14]` 验证。几何顶点、法线和三角绕序由 glTFast 处理，尚未作独立法线逐面验收。

样件含 26 个构件：基础、地板、外墙与南侧两米门洞、楼板开口、东窗、屋顶、8 个 0.5 m 高踏步和椅子代理。源 ID 写入 GLB 节点 extras、manifest 映射和 Unity 场景中的 `WorldBuilderSourceId` 组件。每个网格附一个非凸 MeshCollider。地面是普通网格；本样件不创建 Unity Terrain，也没有导航网格或建筑真实物理材质。固定样件的 0.5 m 踏步已通过下述角色控制器连续路线验证。

## 复现与验证状态

在仓库根目录：

```powershell
$env:PYTHONPATH='src'
python tools/export_unity_sample.py --output artifacts/unity-sample/new-run
```

将新运行的 `library.glb` 与 `manifest.json` 复制到 `adapters/unity/sample_project/Assets/WorldBuilderSample/`，使用 Unity `6000.3.24f1` 打开项目，执行菜单 `World Builder > Build Library Sample`。也可用编辑器 `-batchmode -nographics -projectPath <项目绝对路径> -executeMethod WorldBuilderSampleBuilder.Build -quit -logFile <日志路径>` 批处理；`WORLD_BUILDER_UNITY_VALIDATION` 可指定验证 JSON 输出位置。

本机 v2 批处理记录为 `artifacts/unity-sample/target-validation-v2.json`：`target_load=pass`、`collision=pass`、`orientation=pass`，26/26 构件映射且 26/26 网格有 MeshCollider，编辑器退出码 0。2026-09-23 在 Unity Hub 打开同一项目后，又通过图形界面的 `World Builder > Build Library Sample` 重建场景；`artifacts/unity-sample/target-validation.json` 再次为 26/26、26/26、方向通过。编辑器 Hierarchy 显示 `world_two_storey`、26 个构件、Sun 和 Overview Camera；Scene 视图可见屋顶与东窗，Game 视图可见南立面与门洞。项目 `EditorBuildSettings.asset` 指向 `LibrarySample.unity`；补充保存设置后重跑批处理，`target-validation-final.json` 全项通过、编辑器正常退出码 0。首次图形启动的 Package Manager 在线检索因 `packages.unity.com` 连接重置而报提示，但本地包已注册，样件重建通过。测试 `tests/test_unity_sample.py` 检查 GLB 长度与段、节点 ID、东窗范围、源快照拒绝变更。

2026-09-24 增加独立的 `LibraryWalkValidation.unity` 和 `WorldBuilderWalkValidator`，可通过 `World Builder > Build Library Walk Validation` 或将上述批处理方法改为 `WorldBuilderSampleBuilder.BuildWalkValidation` 重建。验收场景沿用 26 个网格碰撞，另加门外起点地垫、1.8 m 高/0.25 m 半径/0.55 m 跨阶的 CharacterController 和第一人称相机；地垫与控制器只属于验收夹具，不属于 GLB 或通用导出器。进入 Play Mode 后控制器自动连续移动，经 `through_south_door`、`lower_room`、`stair_foot`、`upper_landing` 到 `upper_room`，按坐标、高度和接地条件判定每个检查点，45 秒超时或 5 秒无进展即失败。`artifacts/unity-sample/walk-scene-build-evidence.txt` 摘录脚本重新编译、场景重建并以退出码 0 结束的日志行；图形 Play Mode 的 `walk-validation.json` 记录 `status=pass`、5/5 检查点、终点脚部约 `(14.14,4.28,13.93)`，`walk-validation.png` 是同次运行的 Game View 截图。此结果只通过固定两层样件的室内通行门槛；道路、桥、通用区域、法线逐面检查及与 006/007 同修订联调仍待完成，因此 008 保持 `in_progress`。
