# 047 本周客户端：山谷生成与受限调整

日期：2026-10-16。对应[本周工单](../work_order/047_client_nature_generation_and_adjustments.md)及[独立profile契约](contracts/client047-v0.1.0.md)。本周只接入现有山谷，不宣称实现任意描述生成任意建筑。

同日[048设置修订](14_client048_saved_credentials.md)已新增记住密钥并移除TXT导入；启动入口优先WorldBuilder048。下文包名、TXT功能与截图为047原交付记录，新设置操作以048说明为准，历史证据保留。

## 如何打开与操作

双击项目根目录 [start_client047.cmd](../start_client047.cmd)。它优先启动新版 `dist/WorldBuilder047v2/WorldBuilder047v2.exe`，没有便携包时尝试现有 `.venv-desktop` 源码环境。旧 `WorldBuilder` / 第一版 `WorldBuilder047` 不会随代码更新，勿把它们当本次交付。便携包为 `dist/WorldBuilder047v2-0.1.1-client047-win-x64.zip`，完整解压保留 `_internal`；不需要Unity或Minecraft来预览。

1. 生成入口选择“本周 · 魔法山谷聚落”，默认已经选中。用“离线样例 → 重建山谷示例”无需密钥，重建046录制参数，而非重新调用模型。
2. 用“我的API”时，在设置选“DeepSeek官方预设”；支持本地TXT第一行读入密钥。可以提出本周范围内地形/树林/聚落分布偏好，不能要求机场、现代城市或改变64栋等固定拓扑。范围判定不通过会明确报错。
3. 成功后点击“调整此版本（不调用API）”，展开地形/各聚落/城堡参数，界面标出整数范围。改变参数后点击“生成调整版本”。旧版本保留于运行档案，调整版记录来源。
4. 预览显示实际地形三角网和旋转建筑。拖动左右旋转、上下改变俯仰，滚轮缩放，点击构件查看源ID；“俯视”“地形”“剖切高度”仅改变视图。要滚动整页，请在画布外滚动。
5. 在“交付与诊断”下载WIR世界包/Unity GLB及源JSON。GLB不是完整Unity项目；本周不自动修改现有Unity工程。历史运行可重新打开及精确回放。

“零API”不表示立即完成：当前调整仍做全图构建、通路检查、世界归档与GLB导出，不是局部编辑。此机隔离运行410树调整耗时49.093秒；同时运行多个隔离验证时曾需约4分钟，不能作为固定时延承诺。客户端同一数据目录只允许一个任务。

普通启动历史位于 `%LOCALAPPDATA%/WorldBuilder`。本次验收隔离在 `artifacts/client047/packaged-data`，不混入用户默认档案；当前演示窗口用这个隔离目录。需要重新打开已有演示时，在项目根目录执行：

```powershell
.\dist\WorldBuilder047v2\WorldBuilder047v2.exe --data-dir artifacts/client047/packaged-data
```

## 验证与限制

- 真实HTTP服务/API测试登记在 `benchmarks/client047_live_v1.json`：单个明确参数样本，A/B/D/F各1次，共4次网络调用、6489计账tokens、280.437秒；400树/64栋/两桥/城堡，9461网格，220源房间路线和69室外路线通过。E为已有真实配方复用，不计为本次新API生成。
- 真实API精确回放零网络，worldpkg/GLB/nature_geometry三者一致；证据 `artifacts/client047/live-http-v1/validation.json`。这证明该样本闭环，不代表任意提示词成功率。
- 打包资源独立于工作目录可用：第一版实际768m离线基准自检通过；最终v2在临时目录启动旧45网格样例及回放也通过。最终v2实际桌面操作生成410树调整版，9491网格、零API、源检查通过，来源388树基准保留。后续回放、下载、重开证据见本工单及 `artifacts/client047/validation.json`。
- 新场景 `target_load` / `walkthrough` 均为 `not_run`，本周没有把旧046 Unity实走结论复制给400/410树新版本，也没有自动导入Unity。预览不等于游戏效果或物理验收。

最终8模块回归153项通过，22项交付交叉核对全部通过；3797文件扫描未命中当前密钥。汇总证据为 `artifacts/client047/validation.json`，可用 `tools/check_client047_delivery.py` 在相同验收目录检查（不覆盖已有证据）。原生重开后可见离线基准、410树调整版及其精确回放三条历史；实际界面如下。

![实际客户端预览](../artifacts/client047/client047-overview.png)

![重开后的来源历史](../artifacts/client047/client047-history.png)

旧0.1.0小例入口、旧City/Nature产物及用户sample_project保留。代码和新工单只在本地，未提交/推送。后续通用描述、稳定修订、局部修改、资产库仍分别归029—036/043，不因047完成而置为done。
