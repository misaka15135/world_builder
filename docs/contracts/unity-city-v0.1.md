# Unity 城邦静态区域导出 0.1

本阶段以 `artifacts/benchmark-city-v1/city-first.worldpkg` 的已校验 WIR 城邦为源，导出 512 m 区域的静态 GLB，并在 Unity `6000.3.24f1`、URP `17.3.0`、glTFast `6.20.0` 中实际导入。源世界为 `world_e98d1d4d587fb96f`，源修订为 `revision_c1b82ea36c16a34c95f97c42`。城邦导出器读取 WIR 实体，不使用固定手工样件的 26 构件清单。

## 产物与重建

`artifacts/unity-city/v1/` 包含 `city.glb`、`manifest.json`、`target_profile.json`、`export_report.json`。同一 GLB 和清单复制到 Unity 项目的 `Assets/WorldBuilderCity/`；`CityStatic.unity` 是目标编辑器实际保存的场景。根目录运行：

```powershell
$env:PYTHONPATH='src'
python tools/export_unity_city.py --source artifacts/benchmark-city-v1/city-first.worldpkg --output artifacts/unity-city/new-run
```

将新运行的 `city.glb` 与 `manifest.json` 复制到 `adapters/unity/sample_project/Assets/WorldBuilderCity/`，使用指定编辑器打开项目，执行 `World Builder > Build City Static`。批处理可用 `-batchmode -nographics -quit -projectPath <项目绝对路径> -executeMethod WorldBuilderCityBuilder.Build -logFile <日志路径>`；`WORLD_BUILDER_UNITY_CITY_VALIDATION` 指定验证 JSON 的绝对路径。导出目录必须是新目录，避免悄悄覆盖旧的目标产物。

## 转换边界

176 个 GLB 网格包括 92 条道路、1 座桥、80 栋建筑体量、2 块地表代理和 1 条河道代理。WIR `(东,北,上)` 先转 glTF `(西,上,北)`；目标 glTFast 对 X 轴反射后，Unity 场景为 `(X 东,Y 上,Z 北)`。GLB 节点、清单与 Unity `WorldBuilderSourceId` 组件均保留源实体 ID。每个网格挂 1 个 MeshCollider；区域地面是普通网格，未创建原生 Unity Terrain 或 NavMesh。

损失报告覆盖源包 294 个实体：94 个 `preserved`、82 个 `approximated`、118 个 `omitted`。道路和桥保留源 box 范围；80 栋建筑仅为实体边界的实心代理，未体现门洞、屋顶形状、楼层或室内；地形高程资源被平坦河岸代理替代，河水为半透明长方体；分区、地块、楼层、房间、楼梯和家具均未进入本次 GLB。它们仍在源 WIR 包中。报告状态 `succeeded_with_warnings` 指导出过程，不表示整城漫游通过。

## 本机验证

2026-09-24 对追踪的 `city-first.worldpkg` 重新校验并导出，GLB SHA-256 为 `9fbbe5c489c74ab1566705afa2faa3fd8d305640652599ee33644e205c97be52`。Unity 批处理在 `target-validation.json` 中记录 `target_load=pass`、`collision=pass`、`orientation=pass`，176/176 构件映射、176/176 MeshCollider，桥的目标边界为 X `[252,260]`、Y `[1.6,2]`、Z `[268,274]`，与 WIR 一致；编辑器正常以代码 0 退出。`editor-build-evidence.txt` 保留目标导入与正常退出的日志摘录。`tests/test_unity_city.py` 检查世界包输入、GLB 节点、源 ID、对象级损失报告和桥边界。

2026-09-25 追加 `CityBridgeWalk.unity` 独立运行夹具，可执行菜单 `World Builder > Build City Bridge Walk Validation` 或批处理方法 `WorldBuilderCityBuilder.BuildBridgeWalkValidation` 重建。夹具沿用同一 GLB 和 176 个 MeshCollider，添加高 1.8 m、半径 0.25 m 的 CharacterController，从 `(244,2.1,271)` 出发，沿 WIR `road_cross_west`、`bridge_main`、`road_cross_east` 连续移动。目标检查点为西岸道路 `(248,2,271)`、桥中心 `(256,2,271)`、东岸道路 `(268,2,271)`；每点要求位置、高度及接地，且桥面必须有至少 5 帧接地。35 秒总超时或 5 秒无进展即失败。角色与第一人称相机只属于验收夹具，不包含在 GLB 中。

`artifacts/unity-city/editor-bridge-build-evidence.txt` 记录重建 176 构件、保存场景和编辑器正常以代码 0 退出。随后在 Unity 图形 Play Mode 实走，`artifacts/unity-city/bridge-walk-validation.json` 为 `status=pass`、3/3 检查点、4850 帧接地、桥段 1539 帧接地、零侧向碰撞，终点约 `(267.84,2.08,271)`，同次 Game View 截图为 `bridge-walk-validation.png`。实际目标编辑器曾提示河道代理存在跨度超过 500 单位的大三角形，后续应对长条网格分块并单独验收物理查询稳定性；本次过桥实走通过并不消除该限制。

城邦室内仍是实心建筑代理，未验证进入建筑、上下楼、法线逐面、导航或帧率。008 的最终城邦室内验收仍待后续实现。
