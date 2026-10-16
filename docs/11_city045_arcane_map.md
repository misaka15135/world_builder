# 045：512m 真实 API 魔法城邦

日期：2026-10-16。沿 042 首个详细街区扩规模，目标为 512×512m、48 栋普通住宅/商铺、四广场、一城堡、河道四桥和城墙。模型/本地职责、源端规则和明确限制见 [独立契约](contracts/city045-v0.1.0.md)，过程与当前验收状态见 [045 工单](../work_order/045_api_arcane_large_map.md)。不是默认客户端入口，也不表示其他三类场景全部完成。

## 打开本地成果

2026-10-16用户反馈本版过于平整和规则，新增[046自然版768m地图](12_nature046_organic_map.md)供查看。
本页045保持原场景与机器证据，不能将其历史“待观感确认”理解为用户已接受外观。

现成地图已生成。Windows 在文件夹中双击 [大地图 Unity 启动文件](../tools/open_city045_unity.cmd)。项目沿用独立 `adapters/unity/style042_project`，大地图场景位于 `Assets/Generated/City/ArcaneCity.unity`，不替换原 64m 的 API/Baseline 场景，也不动用户 sample_project。编辑器为 Unity 6000.3.24f1，可传 Unity.exe 路径作为脚本第一个参数或设置 UNITY_EDITOR；也可在 Hub 添加项目并直接打开场景。

真实批次14次网络请求（含1次目录超长拒绝后的预算内重试），本地计账48912 token，295.657s生成有效世界包及9768网格GLB。源172房间路径、Unity全部9768网格加载/重开与9751碰撞体、579渲染批覆盖以及39条代表路线实走通过；物理测试69960帧，56162接地帧。零网络精确回放复现世界包/GLB/源几何，93项针对性回归通过。机器证据汇总为 `artifacts/city045/live-v1/delivery_summary.json`，人工观感仍待用户确认。

进入 Play 后：

- 数字 1：全图俯瞰；2：街面；3：城堡；4：河道。
- WASD 移动，按住鼠标右键转向，Q/E 升降，Shift 加速。
- F 切换步行/飞行。进入步行时回到第一条街道起点，采用 1.8m CharacterController 实体碰撞；它是手动查看模式，不代替自动验收。

普通查看打开 `ArcaneCity.unity`，不要打开自动实走专用 `ArcaneCityWalkValidation.unity`；后者完成时退出 Play（批处理则退出测试进程）。

本次仅本地更改，未自动提交或推送。`City/` 的大体积派生产物仍由忽略规则排除；只克隆先前的 Git 分支不会凭空得到本次地图。

## 产物与验证层级

真实批次在 `artifacts/city045/live-v1/`：`accepted.json`、`city_geometry.json`、`repository/scene.world.json`、自包含 `scene.worldpkg`、`unity/scene.glb`，以及完整调用/失败/配置与代码哈希记录。人工对照为 `offline-v1/`、`offline-v2/`，不混作 API 结果。只看对应最终 `result.json`/`failure.json`，不要把 accepted 参数当成所有后续步骤已完成。

源端检查与 Unity 报告分开。目标证据在真实目录 `unity-evidence/`，包括 `target_validation.json`、独立重开的 `target_reopen.json`、实走 `walk_validation.json` 和 `overview/street/river/castle.png`。证据未产生时不算通过。

源端验证全部普通建筑/主楼房间可达；目标自动实走仅覆盖八配方各一实例的全部房间、主楼、四座桥、两条完整大道/城门及城堡门楼入口。不同实例的全部房间没有逐一目标实走，不能以代表路线外推。渲染按 64m 区域/材料合并，原始构件仍保留 ID、MeshFilter 和非水体碰撞；保存的合并批成员需覆盖每个源网格一次。

颜色材质、阶梯屋顶、盒状树木、平坦地面、直线道路/河道仍是此版本边界；塔楼内部无楼梯、没有战斗/任务/动态水、未迁移 Minecraft。人工观感由用户复核，不用模型 F 的 accept 或网格数量代替。

## 开发复核

```powershell
$env:PYTHONPATH = 'src'
python -m pytest tests/test_city_scene.py -q
python tools/run_city_045.py --check
python tools/prepare_city_045_unity.py --source artifacts/city045/live-v1
```

最后一步仅复制/准备已生成产物，无 API 调用。真实生成需先冻结登记并从本地文件首行读密钥，禁止聊天或提交密钥。已有目录不能覆盖；回放需全部原调用记录和未改动的登记代码，使用新输出目录。当前 v1 的调用预算为最多 28 次、300000 本地计账 token。原始请求/响应和私密文件不上传 Git。
