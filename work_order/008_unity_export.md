# 008 Unity 场景导出与加载验证

- 状态：in_progress
- 创建日期：2026-09-21
- 执行者：root
- 依赖：005；样件试验可与 006 并行，完整验收需要 006、007
- 修改范围：2026-09-25 本阶段由 root 实施五栋已生成室内建筑的 Unity 派生构件与通行验收，涉及 `src/world_builder/adapters/unity/city.py`、`tests/test_unity_city.py`、`adapters/unity/sample_project/Assets/WorldBuilderCity/`、`artifacts/unity-city/`、`docs/contracts/unity-city-v0.1.md` 及 008/000/索引。源 WIR、固定手工样件及 WIR 0.1 Schema 不改；导出版本另起 v2，不覆盖 v1 证据。
- 修改范围：2026-09-25 后续由 root 对其余四栋生成室内建筑逐栋做 Unity Play Mode 通行验收；修改 `WorldBuilderCityV2Builder.cs`、`WorldBuilderCityInteriorWalkValidator.cs`、新场景/运行证据、008/000/索引及 Unity 城邦说明。v2 GLB 与首栋已有证据保持不变。

## 目标与范围

把同一 WIR 修订转成可以在固定 Unity 环境使用的区域场景。

目标编辑器、固定两层样件导入和控制器连续漫游已验证；通用区域导出及与 006/007 同修订的代表性城邦联调尚未实施。

## 本机编辑器子阶段

- [x] ~~停止用户报告有警告的 6000.3.0f1 安装，将目标修订为同一 6.3 LTS 系列的 6000.3.24f1。~~
- [x] ~~安装 6000.3.24f1 并核对 CLI 结构检查、可执行文件版本和 Windows 数字签名。~~
- [x] ~~建立与新版本匹配的 URP/glTFast 精确包配置，并完成手工两层样件实际导入。~~

## 工作项

- [x] ~~固定并记录 Unity、渲染管线、glTF 导入包版本及安装/运行步骤。~~
- [x] ~~005 完成后先转换手工两层建筑样件，验证坐标、门洞、楼梯和基础碰撞，作为 006 扩规模的前置子项。~~
- [ ] 输出分块 GLB、场景清单、对象 ID、材质映射和碰撞描述。
- [ ] 实现 Editor 导入器，恢复场景层次、位置、碰撞与约定的导航设置。
- [ ] 验证坐标、法线、比例、实例化与目标材质降级，生成损失报告。
- [ ] 输出符合 WIR 0.1 `export_report` 的对象映射与损失统计；Unity 反射变换必须处理绕序、法线和切线。
- [ ] 导入与查看器同一修订的代表性城邦并进行漫游与室内可达性验收。

## 城邦静态区域子阶段（2026-09-24）

- [x] ~~从已校验的 512 m WIR 城邦包导出道路、桥、建筑体量和地表/河道代理 GLB，保留源 ID 与修订。~~
- [x] ~~输出符合 WIR 0.1 的逐实体损失报告，明确 80 栋实心代理、平坦地形及未进入场景的室内对象。~~
- [x] ~~在 Unity 6000.3.24f1 实际加载同一城邦修订，核对构件映射、碰撞体和桥的目标边界。~~
- [x] ~~在 Play Mode 连续实走道路和桥，建立可核对的运行证据。~~
- [x] ~~五栋生成室内建筑转为可进入壳体与楼梯，完成首栋道路—门—二层房间目标连续通行。~~
- [x] ~~逐栋验证其余四栋从入口道路经东门和楼梯到二层房间的连续路线。~~
- [ ] 完成分块、法线、导航及 007 同修订联调。

## 验收标准

- 在指定 Unity 版本实际导入，无缺失引用；能够行走道路、过桥、进入室内并上下楼。
- 不对称坐标样例朝向正确；稳定实体 ID 可以追溯至 WIR。
- 明确是否使用普通地形网格，不能把 GLB 导入宣称为自动创建原生 Unity Terrain。
- 场景包包含重建指引、版本配置、报告和验证证据。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-21 | root | 根据正式方案创建后续工单 | 本文件；尚无实现或测试结果 | 依赖满足后认领，执行前重新阅读索引、总规划和本工单 |
| 2026-09-21 | root | 根据独立审查校准规划 | 与正式方案的状态合同、小样先行或需求确认边界保持一致；工单仍为 planned | 对应实施阶段再执行与验证 |
| 2026-09-22 | root | 接收 Unity 6000.3.0f1 候选 profile、坐标合同和能力矩阵 | 版本已冻结但未在 `tx5` 安装验证；`river_bridge` 不对称标记用于坐标检查 | 开工时先验证安装组合和手工样例 |
| 2026-09-23 | root | 按用户授权认领 Unity 目标环境安装阶段 | 本轮范围限于通过已安装 Unity Hub 获取 6000.3.0f1、核对模块与本机版本，并同步工单；场景导出与加载仍待实施 | 检查 Hub 状态和可用安装入口 |
| 2026-09-23 | root | 用 Hub 随附 Unity CLI 预检并启动 6000.3.0f1 安装 | 预检确认 x86_64 编辑器下载量 4,131,048,448 字节、默认安装路径 `C:\Program Files\Unity\Hub\Editor`；CLI 安装进程仍在运行，尚无已安装编辑器证据 | 等待下载与安装完成，运行版本核对 |
| 2026-09-23 | root | 按用户报告的官方签名警告取消旧版本安装并修订目标 profile | 用户停止 6000.3.0f1 后，另行运行的 Unity CLI 下载进程仍在；已中断该进程，CLI `editors --installed` 返回空。Unity 官方发布页与 Hub 正式发行版列表均列出 6000.3.24f1，Hub 列表中该版本无旧版的警告标记；保留旧样例 profile 作为历史输入，新目标版本待实际安装核对 | 预检并安装 6000.3.24f1，核对下载签名和运行结果 |
| 2026-09-23 | root | 预检并启动修订版安装，检查旧缓存清理 | 6000.3.24f1 CLI 预检下载量 4,127,507,400 字节、零警告；新下载已开始。尝试清理旧 6000.3.0f1 的部分下载文件被自动审批以 `blocked by policy` 拒绝，未删除文件；该缓存不作为安装结果 | 等待新版安装并核对数字签名和实际版本 |
| 2026-09-23 | root | 完成 6000.3.24f1 本机编辑器安装与签名核对 | Unity CLI 安装返回 `status=installed`、零错误/警告；`editors --installed` 列出 x86_64 目标，`editors verify` 返回 `ok=true`。完整安装包与 `Editor/Unity.exe` 的 Windows Authenticode 均为 `Valid`，签名者 `Unity Technologies SF`；可执行文件 `ProductVersion=6000.3.24f1_4e7b9b5b6244`。`docs/contracts/environment-baseline.md` 记录实际路径和边界 | 为手工样件建立新版本的 URP/glTFast profile，导入后才可验收 008 |
| 2026-09-23 | root | 按用户“继续推进”认领 Unity 手工样件子阶段 | 本轮修改范围见文件头；本机 6000.3.24f1 附带的 3D Cross Platform 模板 17.0.14 将 URP 固定为 17.0.1；Unity 包注册表显示 glTFast 6.20.0 为稳定版、最低 Unity 6000.0，待实际项目解析确认 | 建立可重现项目，导出样件并在编辑器中加载核对 |
| 2026-09-23 | root | 建立样件项目并首次目标导入 | Unity 批处理首次打开成功，实际包锁为 URP 17.3.0、glTFast 6.20.0。v1 GLB 的 26 个网格均被导入，但不对称东窗校验失败：目标中心为 `(-23.88,6,-13)`，而预期是 `(23.88,6,13)`；这表明 glTFast 在此版本反射 glTF X 轴，导出前的坐标矩阵需调整。失败记录见 `artifacts/unity-sample/editor-build-scene.log` 和 `target-validation.json` | 修正 WIR→glTF 矩阵，生成 v2 后重跑目标导入 |
| 2026-09-23 | root | 修正坐标矩阵并完成 v2 目标导入 | `artifacts/unity-sample/v2/library.glb` SHA-256 `f9dd083acf180287549b23d1aa70e1b0fab4eaa69a484ee4c58e425bb252f75a`；Unity `-executeMethod WorldBuilderSampleBuilder.Build` 退出码 0，`target-validation-v2.json` 记录 26/26 构件映射、26/26 MeshCollider、东窗不对称坐标与实际 prefab 导入均 pass。场景 `adapters/unity/sample_project/Assets/WorldBuilderSample/LibrarySample.unity` 已生成。`pytest tests/test_unity_sample.py` 2 passed；详见 `docs/contracts/unity-sample-v0.1.md`。尚未目视或控制器漫游 | 运行场景，验门洞/楼梯通行；之后才可扩大 006/008 联调范围 |
| 2026-09-23 | root | 收紧样件项目交付范围 | 编辑器生成的本地缓存、解决方案及模板教程/示例资产已加入 `.gitignore`，样件自己的 GLB、场景、脚本和 URP 配置保留；尝试清理本机模板教程/示例资产时自动审批以 `blocked by policy` 拒绝，未删除文件 | 复核包清单和场景引用，保持本机现状 |
| 2026-09-23 | root | 在 Unity 图形界面打开并重建样件 | Hub 识别 `sample_project` 为 Unity 6000.3.24f1 项目；用户授权接受编辑器条款后打开。图形菜单构建再次输出 `artifacts/unity-sample/target-validation.json`：26/26 构件、26/26 MeshCollider、方向 pass；Scene 视图显示屋顶/东窗，Game 视图显示南立面/门洞。包管理器在线检索 `packages.unity.com` 连接重置，但本地包已注册且场景构建成功。构建场景的 Build Settings 改为 `LibrarySample.unity`，不再指向忽略的模板场景 | 下一步加入角色通行验证，门洞与楼梯尚未以控制器连续走通 |
| 2026-09-23 | root | 复核最终项目保存与批处理重建 | `EditorBuildSettings.asset` 指向 `LibrarySample.unity` 的实际 GUID；构建器补充 `AssetDatabase.SaveAssets()` 后重新批处理，`artifacts/unity-sample/target-validation-final.json` 全项 pass，日志以 `return code 0` 结束；完整 Python 回归 63 passed、文档检查 33 Markdown/40 链接/5 JSON/13 工单零错误 | 保持 008 in_progress，下一步验证实际控制器穿门、上楼 |
| 2026-09-24 | root | 按用户要求开始 Unity 连续漫游验收并登记修改范围 | 既有 v2 GLB、26 个 MeshCollider、东窗方向和目标编辑器导入已通过；仍缺从南门到二层的控制器连续运动证据。本轮只新增样件验收场景与控制器，保留原 GLB 和源样例 | 构建可记录控制器碰撞与路线的目标运行场景，在 Unity Play Mode 实走并保存证据 |
| 2026-09-24 | root | 完成固定两层样件的 Unity 控制器漫游 | `LibraryWalkValidation.unity` 使用 1.8 m 高、0.25 m 半径、0.55 m 跨阶的 CharacterController；`walk-scene-build-evidence.txt` 摘录重新编译、重建和退出码 0 的日志。Unity 6000.3.24f1 图形 Play Mode 连续经过南门、一层、楼梯底、二层平台和二层房间；`artifacts/unity-sample/walk-validation.json` 为 `status=pass`、5/5 检查点、终点脚部 Y≈4.28 m；`walk-validation.png` 留下同次运行画面。`pytest tests/test_unity_sample.py` 2 passed，文档检查 33 Markdown/40 链接/5 JSON/13 工单零错误。夹具不属于通用 GLB/导出器 | 固定样件子项完成；008 仍 in_progress，下一步实现通用区域、道路/桥及与 006/007 同修订联调 |
| 2026-09-24 | root | 按用户继续推进认领城邦静态区域子阶段 | 本轮文件范围见文件头；512 m 源端城邦包与固定样件验收证据已具备，目标城邦尚未导出或加载 | 建立真实 WIR 派生 GLB、对象映射与明确损失，再运行 Unity 目标导入 |
| 2026-09-24 | root | 完成 512 m 城邦静态 GLB 与 Unity 目标加载 | `artifacts/unity-city/v1/city.glb` 对应源修订 `revision_c1b82ea36c16a34c95f97c42`，SHA-256 `9fbbe5c489c74ab1566705afa2faa3fd8d305640652599ee33644e205c97be52`；176 个网格、294 实体逐项报告（94 保留/82 近似/118 省略）。Unity 6000.3.24f1 批处理保存 `CityStatic.unity`，`target-validation.json` 为 176/176 ID 与碰撞、桥方向/尺寸、加载全 pass，日志记录退出码 0。Python 全套 `70 passed`，文档检查 34 Markdown/40 链接/5 JSON/13 工单零错误。详情见 `docs/contracts/unity-city-v0.1.md` | 008 保持 in_progress；下一步实际角色跨桥，再实现并验证 5 室内/楼梯、法线与导航；007 尚未提供同修订查看器联调 |
| 2026-09-24 | root | 提交本阶段产物并尝试推送 GitHub | 本地提交完成、工作树干净；三次推送均因 `github.com:443` 连接重置或无法连接失败，远端仍停留在上次提交；没有把未推送内容称为远端成果 | 网络恢复后推送本地 `main`，再继续目标跨桥验收 |
| 2026-09-25 | root | 补推上轮提交并认领城邦跨桥运行验收 | `git push origin main` 成功，远端推进至 `1f5c296`；核对 WIR `road_cross_west`、`bridge_main`、`road_cross_east` 在北向 268—274 m 连续衔接。本阶段修改范围见文件头 | 建立角色路线与独立场景，在 Unity Play Mode 连续过桥并留证 |
| 2026-09-25 | root | 完成 Unity 城邦道路—跨桥 Play Mode 连续验收 | `WorldBuilderCityBuilder.BuildBridgeWalkValidation` 批处理重建 176 构件与独立 `CityBridgeWalk.unity`，正常以代码 0 退出；图形 Play Mode 的 `bridge-walk-validation.json` 为 3/3 检查点、4850 帧接地、桥段 1539 帧接地、零侧向碰撞、`status=pass`，同次 `bridge-walk-validation.png` 留证。源修订仍为 `revision_c1b82ea36c16a34c95f97c42`。Unity 提示河道代理大三角形可能影响物理查询稳定性；本次路线未受阻，不视为普遍排除风险 | 008 保持 in_progress；下一步城邦可进入室内及楼梯、分块/法线/导航与 007 同修订联调 |
| 2026-09-25 | root | 提交跨桥验收产物并尝试推送 | 本地提交完成、工作树干净；前两次 `git push origin main` 分别因连接重置与 `github.com:443` 无法连接失败，远端当前仍为 `1f5c296` | 网络恢复后推送本地跨桥提交；继续室内阶段前重新确认远端状态 |
| 2026-09-25 | root | 认领五栋城邦室内目标验收 | 本次补推 `b529c49` 仍因连接重置失败，本地工作树干净；WIR 首例五栋生成室内建筑均具东侧入口、2 层、预留楼梯洞、20 级直楼梯，参数已核对。本轮文件范围见文件头 | 生成独立 v2 GLB、更新真实对象级损失，再在目标编辑器里实走门洞与楼梯 |
| 2026-09-25 | root | 导出五栋室内并完成 Unity 目标导入 | 独立 v2 GLB 有 346 构件，SHA-256 `31884caef930c85372d42ee62215fda06076bf75d405908a11a0491dab2796fd`；294 实体损失为 94 保留/107 近似/93 省略。Unity 6000.3.24f1 批处理退出码 0，`v2-target-validation.json` 为 346/346 ID/碰撞、东门朝向和五栋 100 级梯级映射 pass | 在图形 Play Mode 实走首栋入口与二层，检查截图与 JSON |
| 2026-09-25 | root | 完成首栋城邦室内的目标连续通行 | `CityInteriorWalk.unity` 图形 Play Mode 从道路穿东门、抵达梯底、登上平台并进入二层房间；`interior-walk-validation.json` 为 5/5 检查点、零侧向碰撞、`status=pass`，末端脚部约 `(25.67,5.28,25.99)`；同次 PNG 留证。其余四栋只通过静态映射，未逐栋实走；长河道网格仍提示大三角形 | 跑完整回归与文档检查；后续验证其余四栋、分块/法线/导航及 007 同修订联调 |
| 2026-09-25 | root | 完成 v2 回归与交接文档 | `python -m pytest -q --basetemp artifacts/pytest-unity-city-full` 为 71 passed；`python tools/check_project_docs.py` 检查 34 Markdown/40 链接/5 JSON/13 工单、零错误。`docs/contracts/unity-city-v0.1.md` 记录重建、目标证据和未验边界，`editor-interior-build-evidence.txt` 留存正常退出日志 | 提交并尝试推送；008 继续 in_progress，后续按未完成项推进 |
| 2026-09-25 | root | 提交并推送室内阶段与先前滞留的跨桥阶段 | 本地提交 `d687581`，`git push origin main` 成功，远端由 `1f5c296` 前进至 `d687581`，包含先前跨桥提交 `b529c49` | 008 继续 in_progress；后续逐栋通行、分块/法线/导航及 007 同修订联调 |
| 2026-09-25 | root | 认领其余四栋室内实走子阶段 | 工作树干净且 `main` 与 `origin/main` 一致；五栋源建筑几何按东向 44 m 等距排列，首栋相同路线已通过。本轮范围见文件头 | 生成四个独立验证场景，在目标编辑器逐栋运行并记录 JSON/截图 |
| 2026-09-25 | root | 完成其余四栋 Unity 室内路线验收 | `WorldBuilderCityV2Builder.BuildRemainingInteriorWalkValidations` 在 Unity 6000.3.24f1 保存四个独立场景并以代码 0 退出；`v2-remaining-target-validation.json` 再次为 346/346 ID/碰撞 pass。四栋各在图形 Play Mode 连续穿东门、上楼进入二层房间，`interior-walk-building-001`—`004.json` 各为 5/5 检查点、零侧向碰撞、`status=pass`，同名 PNG 留证；末端 X 依次约 69.67/113.67/157.67/201.67 m，Y 均约 5.28 m | 008 继续 in_progress；分块/法线/导航及 007 同修订联调待做 |
| 2026-09-25 | root | 复核四栋实走证据与项目文档 | 脚本逐项核对四份 JSON 的源建筑 ID、5/5 检查点、零侧向碰撞、二层终点、高于阈值的楼梯接地帧与 PNG 存在；全部通过。`python tools/check_project_docs.py` 为 34 Markdown/40 链接/5 JSON/13 工单、零错误；本阶段 Python 导出器未改，沿用上轮 71 passed 结果 | 整理提交与推送；008 未完成的目标能力继续留在工单 |

## 交接说明

开始前登记负责人及实际文件范围。完成每个有实际结果的动作后更新记录；通过验收后用 `- [x] ~~工作描述~~` 划掉完成事项，并由协调者同步索引和总规划。
