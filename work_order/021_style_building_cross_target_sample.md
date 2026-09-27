# 021 风格建筑双目标样件

- 状态：done
- 创建日期：2026-09-27
- 执行者：root
- 依赖：017 建筑设计 skill；008 Unity 与 009 Minecraft 已安装的目标环境
- 修改范围：新增独立木构街屋设计/几何/导出脚本、样件测试、`artifacts/building-style-study/`、Unity 样件专用 Assets 及 008/009/017/000/索引记录；不覆盖既有 city、开放空间和手工图书馆样件

## 目标与范围

按 017 的“欧洲中世纪木构街屋”参考卡做一栋沿街店住楼。以同一份版本化样件设计生成 Unity GLB 和 Minecraft Sponge v3 schematic，在 Unity 6000.3.24f1 与 Minecraft Java 1.21.11/WorldEdit 7.3.19 分别实际加载，核对立面、屋顶、室内路线与来源身份。该样件是风格与双目标验证，不代表整个 E 阶段生成器已可自动产生同类建筑。

## 工作项

- [x] ~~固定来源、平面、体量、立面与两层通行路线，登记能力差距。~~
- [x] ~~从同一几何清单导出 GLB、schem、清单与可复核的静态检查。~~
- [x] ~~Unity 目标导入、碰撞、可见外观及通行检查。~~
- [x] ~~Minecraft 目标实贴、可见外观及通行检查。~~
- [x] ~~汇总目标侧证据和下一步设计器/适配器改进项。~~

## 验收标准

- 两份导出清单引用相同样件修订和几何摘要；不覆写既有样件。
- 静态核对门→店面→楼梯→二层，目标侧另记实际加载和通行结果；未实测的项目不能写成通过。
- 能分辨石基、木框架、明色填充、街面开口、上层挑出与双坡屋顶，且有同视角目标截图或明确记录未能取得。

## 执行记录

| 日期 | 执行者 | 动作 | 结果与证据 | 下一步 |
|---|---|---|---|---|
| 2026-09-27 | root | 按用户要求建立独立双目标样件工单，选木构店住街屋 | 参考 [017 风格卡](../skills/building-design/references/historic-and-vernacular.md) 的英格兰木构实例；现有图书馆样件已有双目标通行，但缺街屋的体量与立面表达 | 完成同源样件设计和导出 |
| 2026-09-27 | root | 新建版本化木构街屋双目标导出 | `src/world_builder/samples/street_house.py` 以一份 20×18×12 m 的整数网格表达沿街商铺、后场、上层、四级楼梯开口、木框与挑出坡顶；同源生成 [v1 样件](../artifacts/building-style-study/v1/manifest.json) 的 91 GLB 盒、1,561 个非空气方块、Sponge v3 schematic。几何摘要 `sha256:6a5c5c6aa8bbda083b140bf9acf1eac5b3eb470ad6873a25c10305664afb9a07`，十项离线净空/结构检查均真；此时目标加载均未运行 | Unity 实际导入，再在 Minecraft 实贴 |
| 2026-09-27 | root | Unity v1 导入与观感复核后改 v2 | v1 的 91/91 构件 ID 与 MeshCollider 经另进程重开通过；[正面](../artifacts/building-style-study/v1/unity-street-view.png)与[斜向](../artifacts/building-style-study/v1/unity-oblique-view.png)目标渲染证实有店门、挑出和坡顶，但长侧立面空白、屋面和木框同色混在一起。按此证据调整为深色屋面、连续侧墙梁架、更多侧窗、入口短雨棚、山墙明色填充及烟囱；v2 几何摘要 `sha256:eacb568de7a346d99c0d2a502e2906351138f5ba8ac910f34e4c2a09181d48ec`，123 GLB 盒、1,577 方块。首次 v2 静态检查因一根新斜梁覆盖旧探针而失败，更新探针到相邻未覆盖填充格后通过；定向测试 1 passed。Unity v2 导入 123/123 ID/碰撞通过；schem 已复制到项目 WorldEdit 目录且 SHA-256 与导出一致 | v2 另进程重开与目标渲染；等待 Minecraft 启动器登录后实贴 |
| 2026-09-27 | root | Unity v2 重开与外观复核 | [重开 JSON](../artifacts/building-style-study/v2/unity-reopen-validation.json) 为 123/123 来源 ID 与碰撞体 `pass`，另进程保存场景重新加载成功；[v2 斜向目标图](../artifacts/building-style-study/v2/unity-oblique-view.png)可见明色山墙、深色屋面、木框侧面、挑出、入口雨棚与烟囱。仍为盒体近似，缺真实斜撑、瓦片、门扇；Unity 玩家通行未验。Minecraft 启动器自动恢复登录，但点现有 Fabric 配置后出现“可能不支持最新玩家安全特性”的确认框；`computer-use` 规则要求用户确认接受第三方警告，已发出问题，未点继续 | 得到用户确认后进游戏实贴；补目标通行并汇总差距 |
| 2026-09-27 | root | 双端静态完整性检查 | `tests/test_style_building.py` 对两次导出的设计/GLB/schem 字节一致性、GLB 节点数、Sponge v3 NBT 与关键方块做核对；首次使用 pytest 默认 `%TEMP%` 因 `PermissionError` 未进入测试体，改用仓库内独立 `--basetemp` 后专项 2 passed（含 skill 链接测试）。`tools/check_project_docs.py` 检查 88 Markdown/125 本地链接/6 JSON/22 工单，零错误 | 目标游戏确认后实贴 |
| 2026-09-27 | root | 在 Unity 建立真实 CharacterController 通行场景并迭代入口 | v3 将 Unity 楼梯实体分为半阶后，`unity-walk-validation.json` 在街面停住；v4 抬高入口雨棚，角色到达门前但停在 z=2.71。增加碰撞诊断后查明撞到门顶横梁 `street_house_part_049`，不是雨棚。v5 将门洞 y=1..3 三格保持为空，静态门洞检查同步扩大；v5 双端导出摘要 `sha256:feaace6e5af87e8d1d54a1265a2ff04e4dd9306193fa1b33afa6b3a6338627a6`，143 GLB 构件、1,571 非空气方块，专项测试 2 passed。各失败结果留在 v3/v4 目录 | 重新导入 v5 并进行连续通行验证；Minecraft 警告确认后实贴 |
| 2026-09-27 | root | 完成 v5 Unity 目标复验 | [导入](../artifacts/building-style-study/v5/unity-build-validation.json)及[另进程重开](../artifacts/building-style-study/v5/unity-reopen-validation.json)均 143/143 来源 ID 与碰撞体通过；[Play Mode 通行](../artifacts/building-style-study/v5/unity-walk-validation.json)由 1.8 m CharacterController 连续经过街道、门、店面、楼梯、上层平台与房间，`status=pass`、6/6 检查点、326 帧楼梯支撑、0 帧侧向阻挡。[目标斜向截图](../artifacts/building-style-study/v5/unity-oblique-view.png)显示石基、明色填充、木框、挑出、深色双坡屋顶与烟囱；仍是盒体近似 | Minecraft 实贴与玩家通行；再汇总设计器可复用改进 |
| 2026-09-27 | root | 核对 Minecraft v5 安装位置与阶段文档 | v5 `.schem` 与独立 WorldEdit 目录副本 SHA-256 均为 `707af8f5a29074f3abf862562542a8a1ef5d4bccce01ea1f2fb3c6b5d42dc8ae`；启动器当前仍显示修改配置警告，未点击确认。项目文档检查 88 Markdown/132 本地链接/6 JSON/22 工单零错误；`git diff --check` 通过，仅提示现有文件将来可能转 CRLF | 收到用户对警告的明确确认后启动 Minecraft，实贴并复核 |
| 2026-09-27 | root | 用户已明确确认启动修改过的 Fabric 配置；继续 Minecraft 目标验证 | 保持本工单 `in_progress`，本阶段仅在独立测试世界区域贴 v5 样件、截图、检查方块与通行；不修改已有城邦和图书馆样件 | 点击启动器确认，进入游戏后核对 WorldEdit 与测试世界 |
| 2026-09-27 | root | Minecraft 1.21.11/Fabric/WorldEdit 实际加载并粘贴 v5 | 已进入 `WB Verify Flat`，在远离现有城邦的 `(3000,-61,3000)` 以旁观模式执行 `//schem load street_house_study_v5`，游戏回报加载成功；`//paste -a` 回报粘贴点 `(3000,-61,3000)`、`1571 blocks affected`、0 生物群系/实体，恰与 v5 清单非空气数一致。尚未完成截图、方块探针与玩家通行 | 调整视角留外观/室内图，检查关键方块并实走 |
| 2026-09-27 | root | Minecraft 目标外观与生存模式通行完成 | [目标验证 JSON](../artifacts/building-style-study/v5/minecraft-target-validation.json)记录手工读取的 F3 检查点：从 `(3008.5,-60,3019.5)` 出发，英文键盘连续移动穿过南门到 `(3008.5,-60,3013.683)`，横移至梯脚 `(3013.761,-60,3012.422)`，沿原生楼梯上至二层平台 `(3013.761,-56,3007.933)`，进入上层居室 `(3011.024,-56,3009.824)`；出发至居室间无传送、跳跃。早期按键无位移查明是中文输入法组合文字拦截，切英文后重试成功。[外观截图](../artifacts/building-style-study/v5/minecraft-oblique-view.png)及[F3 室内检查点](../artifacts/building-style-study/v5/minecraft-upper-room-checkpoint.png)已保存；[夜视布局图](../artifacts/building-style-study/v5/minecraft-upper-room-night-vision.png)仅用于展示暗处平面，不代表自然照明。`latest.log` 的加载、粘贴点与 1,571 方块回报摘录见[证据文本](../artifacts/building-style-study/v5/minecraft-paste-evidence.txt)，玩家名与用户目录已遮盖 | 本工单样件验收完成；将室内照明、门扇/斜撑/瓦片、模板化与 WIR 接入交后续工单 |
| 2026-09-27 | root | 同步总规划、索引及双目标工单并复核 | 专项 `tests/test_style_building.py` + `test_building_skill.py` 为 2 passed；`minecraft-target-validation.json` 通过 JSON 解析；项目文档检查 88 Markdown/139 本地链接/6 JSON/22 工单、零错误；`git diff --check` 无格式错误（仅现有文件 LF/CRLF 提示）。021 已置 `done`，008/009/017 仍负责通用能力 | 后续从 017 的照明、立面词汇与自动风格选择开始 |

## 目标侧结论与后续改进

- 同一整数网格的 v5 设计、GLB 和 Sponge v3 文件共有几何摘要 `sha256:feaace6e5af87e8d1d54a1265a2ff04e4dd9306193fa1b33afa6b3a6338627a6`。Unity 143/143 构件导入与重开、控制器 6/6 路线通过；Minecraft 1,571 方块实贴与生存模式同路径通过。目标侧证明的是这栋手工样件的导出与通行，不等于 E 设计器可自动生成该风格。
- 外观能读出木框、明色填充、街面开口、上层挑出、双坡屋面与烟囱，但屋面是退台方块、立面缺斜撑/门扇/瓦片层次；Minecraft 居室缺固定照明，自然状态偏暗。优先把入口净空、逐层楼梯井、采光与照明变成设计器和目标适配器可检查的字段，再增加可复用的立面/屋顶词汇与风格参考选择。文献只给案例特征，尺寸与布置仍属本样件的设计判断。

## 交接说明

样件优先复用已验证的 GLB 和 Sponge v3 写入路径；适配器中的通用自动风格选择、多层通行与 512 m 城市场景不在本工单验收范围。
