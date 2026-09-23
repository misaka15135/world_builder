# 009 两层建筑 Minecraft 样件导出

状态：受限离线样件已实现，目标软件加载与玩家通行尚未验收。日期：2026-09-23。适配器版本：`0.1.0-sample.1`；源 WIR Schema：0.1.0。

## 来源与适用边界

输入固定为 [两层建筑手工样件](../../examples/two_storey_building.world.json) 的 `revision_two_storey_001`。适配器校验整个样件的规范 JSON 摘要；几何、版本或任何源记录改变后会拒绝导出，必须审查并发布新映射。源坐标为右手系 X 东/Y 北/Z 上，单位米；目标坐标为 X 东/Y 上/Z 南，按 `(x, z, -y)` 映射，1 米对应 1 方块。

Sponge [Schematic v3 官方规范](https://github.com/SpongePowered/Schematic-Specification/blob/master/versions/schematic-3.md)规定 GZip NBT、`Schematic` 根内复合标签、维度、`DataVersion`、`Blocks.Palette` 和按 `x + z×Width + y×Width×Length` 排列的 varint 方块数据。WorldEdit [7.3.19 命令文档](https://worldedit.enginehub.org/en/7.3.19/commands/)列出 `/schem load`；[项目变更记录](https://github.com/EngineHub/WorldEdit/blob/version/7.4.x/CHANGELOG.txt)记载 7.3.18 添加 1.21.11 支持，7.3.19 是后续 7.3 系列版本。来源访问日期均为 2026-09-23。规范和维护方记录说明目标格式与候选版本，并不构成本机加载成功证据。

手工源仅有建筑/房间体积、楼梯关系与家具资产引用，没有墙、门、楼板开口或梯段实体参数。这里明确采用样件专用的设计判断：生成 20×9×16 方块石砖外壳、南门、上下层地板和屋顶、东侧非对称玻璃窗、两格宽的四级北向楼梯及开口。1.4 米源楼梯净宽量化为 2 方块；源 4 米上层标高采用目标 y=3 的楼板上表面 y=4。链接的椅子 GLB 不在样件内，替换为西向橡木楼梯块。全部替代均列在 `export_report.json`，没有把模板推断称作已保留的源几何。

## 运行与文件

在项目根目录运行：

```powershell
$env:PYTHONPATH = 'src'
python tools/export_minecraft.py --source examples/two_storey_building.world.json --output artifacts/my-minecraft-sample --data-version 4671
```

`--data-version` 必须显式提供正整数；上例的 `4671` 只用于当前离线试验，未在本机目标安装核对。导出器不替用户推断目标运行时版本。输出目录必须不存在，避免覆盖已有证据。文件有 `library.schem`、`manifest.json` 和 `export_report.json`：manifest 记录源修订/摘要、目标原点 `[4,0,-18]`、尺寸、方块数、Schematic 哈希、离线检查与目标加载状态；报告符合 WIR 0.1 `export_report` 形状，源快照不被修改。文件是区域剪贴板，不是独立 Minecraft 世界目录。

离线检查逐格验证门洞到上层房间的连续路径、至少两格头部净空与每级不超过一格的高度变化；独立测试解析 GZip/NBT、palette、varint 索引、门洞、窗、楼梯和楼板开口。它没有模拟 Minecraft 碰撞形状、导航、流体或实体行为，不能代替实际玩家通行。

## 目标验证待办

本机 `.minecraft/versions` 检查仅见 26.2、26.3 和 26.3 快照，没有冻结的 Minecraft 1.21.11/WorldEdit 7.3.19 组合。官方客户端 JAR 下载核对 `DataVersion` 的尝试被自动审批阻止。因此 `manifest.json` 的 `data_version_verified_on_target` 为 `false`，`game_load` 和 `in_game_walk` 均为 `not_run`。

在目标组合可用后，应先从该安装确认 `DataVersion`，用确认值重新导出；将 `.schem` 放到 WorldEdit 配置的 `schematics` 目录，执行 `/schem load library`，在新测试世界按 manifest 原点放置并实际穿过门、走完楼梯、进入上层房间，记录加载日志与截图/视频。WorldEdit 的[剪贴板文档](https://worldedit.enginehub.org/en/7.3.19/usage/clipboard/)说明配置目录和加载/粘贴流程。只有这些动作成功，009 的目标加载与玩家通行子项才可勾选。
