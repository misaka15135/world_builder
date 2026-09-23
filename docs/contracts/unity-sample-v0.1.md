# Unity 两层建筑目标样件 0.1

本样件是 008 的手工两层建筑目标试验，不是任意 WIR 城邦导出器。输入固定为 `examples/two_storey_building.world.json` 的 `revision_two_storey_001`。源端只给出建筑、房间、楼梯的体积和关系，没有墙、门、踏步或完整家具几何，因此导出器明确采用样件级构造规则，并在对象级报告中记为 `approximated`。

## 版本与产物

2026-09-23 本机 `MISAKA` 使用 Unity `6000.3.24f1`。仓库中的 Unity 项目位于 `adapters/unity/sample_project/`，首次打开后 `Packages/manifest.json` 与锁文件实际固定 URP `17.3.0`、glTFast `6.20.0`。前者由目标编辑器将随附模板原有 `17.0.1` 升级至 `17.3.0`；后者来自 Unity 包注册表，最低编辑器版本为 `6000.0`。这些是样件的实际包版本，不沿用旧的 Unity `6000.3.0f1` 历史 profile。

`artifacts/unity-sample/v2/library.glb` 为 glTF 2.0 二进制，SHA-256 为 `f9dd083acf180287549b23d1aa70e1b0fab4eaa69a484ee4c58e425bb252f75a`；同目录包含 `manifest.json`、`target_profile.json` 和符合 WIR 0.1 记录结构的 `export_report.json`。导出器为 `src/world_builder/adapters/unity/sample.py`，命令入口为 `tools/export_unity_sample.py`。同一 GLB 与 manifest 复制到 Unity 项目的 `Assets/WorldBuilderSample/`，由 glTFast 作为原生 Prefab 导入；`WorldBuilderSampleBuilder` 建立场景、对象 ID 组件和 MeshCollider。`LibrarySample.unity` 是实际生成的场景文件。

## 坐标与几何

WIR 为右手系、米单位，坐标为 `(东, 北, 上)`。目标 Unity 场景约定 `(X 东, Y 上, Z 北)`，行主序 4×4 映射为 `[1,0,0,0; 0,0,1,0; 0,1,0,0; 0,0,0,1]`，行列式为负。glTF 文件自身为右手 Y-up；导出前使用 `(西, 上, 北)`，即 `[-1,0,0; 0,0,1; 0,1,0]`，其行列式为正。目标 glTFast `6.20.0` 在导入时反射 X 轴，构成最终的 Unity 映射。v1 曾按反射 Z 轴的假设输出，实际东窗出现在 `(-23.88,6,-13)`；v2 通过导入后东窗边界 `[23.75,5,12]` 至 `[24,7,14]` 验证。几何顶点、法线和三角绕序由 glTFast 处理，尚未作独立法线逐面验收。

样件含 26 个构件：基础、地板、外墙与南侧两米门洞、楼板开口、东窗、屋顶、8 个 0.5 m 高踏步和椅子代理。源 ID 写入 GLB 节点 extras、manifest 映射和 Unity 场景中的 `WorldBuilderSourceId` 组件。每个网格附一个非凸 MeshCollider。地面是普通网格；本样件不创建 Unity Terrain，也没有导航网格或建筑真实物理材质。0.5 m 踏步较陡，能否由游戏控制器连续走上楼仍需实际漫游验证。

## 复现与验证状态

在仓库根目录：

```powershell
$env:PYTHONPATH='src'
python tools/export_unity_sample.py --output artifacts/unity-sample/new-run
```

将新运行的 `library.glb` 与 `manifest.json` 复制到 `adapters/unity/sample_project/Assets/WorldBuilderSample/`，使用 Unity `6000.3.24f1` 打开项目，执行菜单 `World Builder > Build Library Sample`。也可用编辑器 `-batchmode -nographics -projectPath <项目绝对路径> -executeMethod WorldBuilderSampleBuilder.Build -quit -logFile <日志路径>` 批处理；`WORLD_BUILDER_UNITY_VALIDATION` 可指定验证 JSON 输出位置。

本机 v2 批处理记录为 `artifacts/unity-sample/target-validation-v2.json`：`target_load=pass`、`collision=pass`、`orientation=pass`，26/26 构件映射且 26/26 网格有 MeshCollider，编辑器退出码 0。2026-09-23 在 Unity Hub 打开同一项目后，又通过图形界面的 `World Builder > Build Library Sample` 重建场景；`artifacts/unity-sample/target-validation.json` 再次为 26/26、26/26、方向通过。编辑器 Hierarchy 显示 `world_two_storey`、26 个构件、Sun 和 Overview Camera；Scene 视图可见屋顶与东窗，Game 视图可见南立面与门洞。项目 `EditorBuildSettings.asset` 指向 `LibrarySample.unity`；补充保存设置后重跑批处理，`target-validation-final.json` 全项通过、编辑器正常退出码 0。首次图形启动的 Package Manager 在线检索因 `packages.unity.com` 连接重置而报提示，但本地包已注册，样件重建通过。测试 `tests/test_unity_sample.py` 检查 GLB 长度与段、节点 ID、东窗范围、源快照拒绝变更。尚无角色控制器的连续穿门、上楼漫游证据；因此 008 保持 `in_progress`。
