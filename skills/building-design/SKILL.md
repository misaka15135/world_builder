---
name: building-design
description: How to design a single building that reads as a real one in Minecraft - massing, proportion, facade depth, roof and palette, entrance, vertical circulation and interiors - expressed in this project's design schema. Use when stage E designs, extends or reviews a building (templates in settings/*/designs.json, plans in planning/designer.py, or judging a rendered result).
metadata:
  short-description: Design rules for stage E buildings
---

# 单栋建筑的设计规则（阶段 E）

用途：E 阶段产出或审视一栋建筑时，用它判断"这栋好不好、哪里不对、下一步改什么"。规则尽量给**可核对的数字**，并指出在 `settings/<id>/designs.json` 与 `planning/designer.py` 里怎么表达。

## 1. 产物必须包含什么

外形（各层轮廓与退台）→ 层数与层高 → 每层房间与用途 → **每层可达的竖向交通** → 入口（门宽/门高/门垛/朝向）→ 屋顶原型 → 材质 → 家具。任何一项缺失都算没做完，而不是"以后再说"。

## 2. 十条规则

1. **体量（massing）**：一栋建筑由 2—4 个体量组成，而不是一个盒子——主体 + 至少一个附属体量（塔楼、侧翼、门廊、外楼梯、烟囱）。附属体量的高度与进深要和主体**不同**（相差 ≥ 2 m 或 ≥ 20%），否则读起来还是同一个盒子。表达方式：`design_compound` 的多体量，或主体上的退台 + 屋顶原型组合。
2. **比例**：开间 : 进深取 1.0—1.6；层高 ≥ 3.0 m（目标适配器把门洞量化成 2 格，地坪占第 0 行，首层低于 3.0 m 会被拒收）；门窗高度 ≤ 层高的 60%，否则墙面读起来像玻璃棚。
3. **立面要有深度**：外墙至少两处凹凸或线脚。当前适配器可用的手段：**腰线**（每层一道 1 格的木/玻璃带）、**出檐 ≥ 0.6 m**、**勒脚**（首层用更暗更粗糙的材质）、**角柱**（转角 1 格竖线）、门窗内凹 0.3 m。全部都是盒体，做不出的凹凸就不要写在文档里当已实现能力。
4. **屋顶**：古代风格双坡 1.2—1.6 m 或尖塔 2.4—3.0 m，现代平顶 0.4—0.5 m 加女儿墙；**檐口必须出挑**（≥0.6 m），否则檐口线消失、立面变成一张纸；屋顶高度不计入层高，但要计入包络。
5. **材质 3—4 种**：主材（墙体）+ 辅材（勒脚/角柱）+ 装饰（腰线/窗框）+ 屋顶。区分靠**明度**而不是色相；同一栋楼不要超过 4 种，超过就读成杂乱。
6. **入口**：门宽 2.0 m、高 2.4 m、门垛 ≥ 1.0 m、离墙角 ≥ 0.3 m（目标适配器硬规则，短墙面必须改挂最长的一面）；入口要有台阶或门廊，不能平贴在地面上。
7. **竖向交通**：**每一层都要有可达的楼梯**，楼梯落点与楼板开口对齐，井不出外墙。当前 `design_open_space`/`design_building` 只产一部到达二层的楼梯——这是必须补的缺陷，不是可接受现状。
8. **室内**：每层 ≥ 2 间有用途的房间 + 一条通道；家具放在房间里且不挡门、不占通道；房间用途与建筑功能一致（旅店要有客房、公会要有任务板）。
9. **采光**：沿外墙每 6—8 m 一扇窗；室内拐角留光源位；不要靠"整面墙都是玻璃"解决采光。
10. **与环境的关系**：贴街的一侧做门面（入口、窗、腰线都在这一侧），背面可以简化；地块窄就做长条 + 山墙，宽就做围合院落；建筑高度与相邻建筑相差 ≤ 1 层，避免突兀。

## 3. 校验清单

设计产出后逐条核对（括号内是本项目已有的机器校验规则）：

- 轮廓与体积不出包络、不超高（`design.outline`、`design.volumes_inside`、`design.height`）
- 入口在合法墙面上（`target.building_entry`，源端对应 `design.entry`）
- 楼梯井在壳体内部、梯段装得下（`design.stair_void`、`design.stair_fits_void`、`target.interior_void`）
- 房间在楼层内且不重叠（`design.rooms_inside`、`design.partition`）
- 家具在房间里（`design.furniture`）
- 多体量互不重叠、角色齐备（`design.volumes_clear`、`design.parts`）

## 4. 当前能力边界（不要写成已实现）

适配器只支持**轴对齐盒体 + 逐层退台 + flat/gable/spire 三种屋顶**。圆柱（储罐）、自由曲面（船体）、下沉开挖（干船坞）、悬挑与斜撑都**还没有**。所以现在要"好看"，只能靠：体量组合、立面深度（腰线/出檐/勒脚/角柱）、材质对比、屋顶原型、以及与环境的关系。任何依赖新几何词汇的想法，先写进工单再实现。

## 5. 来源

- Minecraft Wiki《Tutorial:Construction》：<https://minecraft.wiki/w/Tutorial:Construction>，2026-09-27 通过阅读代理取到（直连被 Cloudflare 403）。**适用边界**：该页面向生存建造（地洞、简易小屋、围墙、城堡），材质与结构词汇可用，但**不提供美学比例规则**。
- 未能取得的来源（如实记录）：`Tutorial:Building tips`、`Tutorial:Roofing`、`Tutorial:Decoration`、`Tutorial:Landscaping` 在 minecraft.wiki 上不存在或取不到；DuckDuckGo 搜索返回人机验证，**按规则不去破解**，因此没有引用社区教程。
- 项目内证据（已实测）：出檐 0.6 m 与逐层腰线（适配器 `0.1.0-city.4`）、三种屋顶原型、入口面与门垛硬规则（`target.building_entry`，2026-09-27 两次实测中断）、楼梯井与梯段校验（`design.stair_fits_void`）、道路"外接盒折叠"缺陷（工单 020）。见 `work_order/006`、`009`、`017`、`020`。
- **设计判断**（不属于上述来源）：第 2 节里"开间:进深 1.0—1.6""每 6—8 m 一扇窗""高度差 ≤ 1 层""材质 ≤ 4 种"这几条是依据项目经验给出的经验值，尚未逐条做对照实验。
