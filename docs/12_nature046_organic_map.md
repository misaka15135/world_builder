# 046 起伏山谷与非规则聚落地图

2026-10-16，本地独立改进案例；对应 [046](../work_order/046_organic_terrain_map.md)，
[版本契约](contracts/nature046-v0.1.0.md)。旧 [045平地图](11_city045_arcane_map.md)保留不覆盖。

## 怎么打开

双击 [自然版Unity入口](../tools/open_nature046_unity.cmd)。它使用本机Unity
`D:\Unity\6000.3.24f1\Editor\Unity.exe`，打开仓库内独立 `style042_project`。
已打开该项目时，在Project面板打开
`Assets/Generated/Nature046/ArcaneNature046.unity`，或菜单 `World Builder → 046 → Open Organic Landscape`。
这不是用户原来的 `sample_project`。

按Play后：1全图、2聚落、3城堡、4河谷；WASD配合右键看向、Q/E升降、Shift加速。
F切到地面步行，出生在西南聚落广场，再按F恢复飞行。未按Play时可用Scene视图通常操作。
正常场景与自动验证用 `ArcaneNature046WalkValidation.unity` 分开，后者会自动行走并结束Play。

本轮源码和派生资源尚未提交/推送。`Assets/Generated/Nature046`、原始调用与
`artifacts/nature046`保持本地；不能声称仅Git克隆就有生成好的场景。

## 与上一版的差异

- 区域从512×512m扩大为768×768m，面积2.25倍。
- 2m采样的真实三角网起伏地形，弯曲河床与静态水面、两座桥，不再是整块平板。
- 64栋不同朝向/尺寸的住宅商铺分布在四个非行列聚落，地基顺地势整平；山丘城堡、广场和森林。
- 地形寻路形成的道路避让建筑，路面直接属于地形网格；源数据中保存真实旋转几何而非只改Unity摆放。

这些是几何和布局改进，材质仍为低多边形纯色风格。道路边缘有2m栅格特征，聚落仍有明确中心；
尚未实现自然路沿平滑、手工美术资产、照片级纹理或开放式建筑生成。

桥头整平地表与桥面同高以保证步行连续；Unity对桥的专用不透明材质采用微小深度偏移，
解决重叠面的渲染闪烁，不移动源网格/碰撞体、不改变原始GLB或通行高程。

## 复现入口

```powershell
.venv/Scripts/python.exe -m pytest tests/test_nature_scene.py -q
.venv/Scripts/python.exe tools/run_nature_046.py --offline --output artifacts/nature046/my-offline
.venv/Scripts/python.exe tools/run_nature_046.py --check
.venv/Scripts/python.exe tools/prepare_nature_046_unity.py --source artifacts/nature046/live-v3
```

真实交付批次位于 `artifacts/nature046/live-v3`；`live-v1`保留F超长失败。
`v2`完成源导出，但在旧离线目标发现横坡问题，因此不是交付版；冻结源码另存，不覆盖其产物。
`v3`使用046.2完整坡度选路，复用请求完全相同的B/D响应，F重新审查新构建报告，保留累计调用和前序上下文。
所有B/D/E/F模型响应与新代码/配置/技能哈希通过登记和源快照溯源，不能把离线对照标成真调用。

```powershell
.venv/Scripts/python.exe tools/run_nature_046.py --batch v3 --replay artifacts/nature046/live-v3 --output artifacts/nature046/my-replay
```

回放要求冻结代码不变，输出到新目录，零网络核对worldpkg、GLB和源几何字节一致。
新付费批次必须先离线检查、再登记新的batch，并用 `--key-file C:/Users/rjc/Desktop/api.txt`，
只读第一行，不能把密钥放进聊天、登记或Git。再次调用与本次复现是不同工作，不需为查看重付费。

## 验收分层

本次最终源为768m、64栋普通建筑、一座城堡、两座桥、388棵树，地形高差71.086m；
44种5度朝向分桶、220条源房间图和69条源室外路线通过。源网格9425件（9420实心件）。
最终真实运行250.078s、3条任务响应（B/D精确复用、F新调用1次），5041本地计账token含复用；
含前序失败/修订总共6次实际API调用、10379服务端报告token，不能把复用重复加成供应商账单。
101项针对性回归通过；worldpkg/GLB/源几何零网络逐字节回放通过。
Unity6000.3.24f1完成全部网格bounds加载/独立重开，45/45代表路线实走，85479帧、73030接地帧。
世界 `world_d4b44d99c76e0c1fadb6e453`，修订 `revision_d4b44d99c76e0c1fadb6e453`。
worldpkg SHA-256 `a2fc1687613342beb137de9b673d7e6a72d49a76b55726988ef70168ee804a67`；
GLB SHA-256 `d38b834fc1fb532106da6ff8efc9793ebe7d63664b5b0dd07a87eac679df8459`。

运行的模型仅B/D/F；详细E取自045九个真实配方，不声称每栋重新设计、通用A—F或四旧场景已完成。
源端检查全部房间局部图、旋转后的世界路线、入口、路网、坡度与水体避让；Unity逐构件验证加载/
保存重开与碰撞体，并实际走每配方一个代表全部房间、城堡主楼、主坡路/跨河/入口/城堡引道。
目标代表不等于64栋全部目标实走；F的文字审查不等于物理验证。实际证据聚合在
`live-v3/delivery_summary.json`，截图在 `live-v3/unity-evidence`，观感由用户复核。

042/024仍in_progress，043建筑库/外部能力检索仍planned；本轮不启动该后置方向。
