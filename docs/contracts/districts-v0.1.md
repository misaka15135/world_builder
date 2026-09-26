# 区块归属与选址 0.1

版本：0.1.0。日期：2026-09-26。实现：`src/world_builder/planning/siting.py`、`settings/*/districts.json`、`tools/plan_districts.py`。状态：**离线规则路径已实现并测试；街区是矩形、本地路网仍在轴上。**

本文是流水线阶段 D（[016](../../work_order/016_district_siting.md)）的合同。上游见 [scene-brief-v0.1.md](scene-brief-v0.1.md)（简报与目录）与 [terrain-plan-v0.1.md](terrain-plan-v0.1.md)（地形）。

## 1. `districts.json`

```json
{
  "districts_version": "0.1.0",
  "setting": "arcane_medieval",
  "block_area_m2": [2500, 18000],
  "target_blocks": [40, 70],
  "uses": {
    "civic": {"share": [0.08, 0.20], "centre_distance": [0.0, 0.25], "road_width_m": 8,
              "height_factor": 1.0, "footprint_factor": 1.0}
  },
  "domains": {
    "castle": {"kind": "castle", "height_factor": 1.25, "footprint_factor": 1.15, "prefers": ["civic", "green"]}
  },
  "roads": {"arterial_width_m": [6, 10], "local_width_m": [3, 5]}
}
```

- `uses`：每种用途的**街区占比**（校验器会核对实际占比）、理想中心距、路宽、以及该用途的高度/占地上限系数。`wants_water: true` 的用途会被禁止落在离水 150 m 之外。
- `domains`：**归属层**。每个 domain 有自己的高度与占地系数、偏好的用途，并拥有若干街区——这就是"若干街区同属一个城堡/港务局/工业区"。
- 四种背景各有一份：魔法城邦（城堡 / 行会区 / 外城），现代都市（商务核心区 / 滨河区 / 外围城区），工业园（厂区 / 货场带 / 工人住区），港口（港务局 / 码头带 / 城区）。

## 2. 产物

| 产物 | 含义 |
|---|---|
| `domains[]` | 归属：`kind`、高度/占地系数、偏好用途、拥有的 `block_ids`、中心 |
| `blocks[]` | 大小不一的矩形街区：`use`、`domain`、面积 |
| `roads[]` | `arterial` / `local` / `quay` / `rail` / `rail_spur`：折线、宽度、等级 |
| `bridges[]` | 每条跨水的桥：所属道路、跨越的水道、跨度起止、宽度 |
| `sites[]` | **每栋建筑一个包络**：矩形、`max_height_m`、`max_storeys`、所属街区与 domain、`needs`、`adjacency` |
| `works[]` | 线性工程与船舶：城墙、码头、岸壁、铁路、地铁、货轮（走廊/泊位，不是地块） |

## 3. 生成规则（可复现）

1. **街区**：递归二分（BSP）到声明面积区间，切点带抖动，因此街区大小不一而不是等距网格；每个街区记录用途与实际面积。
2. **用途**：按 `uses.share` 取配额，再按"中心距适配 + 临水适配 + 平坦度"打分贪心分配；临水用途在内陆街区上被直接禁用。
3. **归属**：每个 domain 先锚定它最合适的街区，然后所有街区按"偏好用途 + 到锚点距离"归属；**每个 domain 至少要有一个街区**，否则它的系数只是装饰。
4. **骨架**：一条**多段折线干道**串联各 domain 锚点并延伸到图外（因此天然非正交，且每次转向都记录在 `arterial_headings_deg`）；每个街区有临街路、内部脊路、连接干道的支路；港区有顺岸路（`quay`），需要铁路的背景有贯穿货场的走行线与场区专用线（`rail_spur`）。跨水处按 4 m 采样切出**一段一桥**。
5. **选址**：按需求顺序放置——先是"锚点"类（广场、公园等无邻近要求的），再是**临水/占地最大**的（干船坞、堆场、厂房），最后是普通建筑；有 `adjacency` 的类型在伙伴就位后再放。每栋在街区内部按网格排布，**临水的从靠水那格开始填**。
6. **包络**：面积用目录区间中值 × domain 与用途的占地系数，再夹回目录区间（目录是硬约束）；高度同理，并换算层数。**硬筛**：临水/临岸/居中/临铁路的场址要求不满足就不放这一格，放不下就在 `siting.sites_present` 里如实报缺。

## 4. 独立校验（`siting.*`）

| 规则 | 判据 |
|---|---|
| `blocks_tile` / `block_area` | 街区无缝覆盖全图且不重叠；面积落在声明区间（边缘允许半块） |
| `use_share` | 每种用途的实际街区占比落在 `share` ±0.05 |
| `domains` | 每个街区恰好有一个归属；每个声明的 domain 都有街区 |
| `domain_factors_applied` | 用**"实测高度 ÷ 该类型目录中值"**的中位数比较两个 domain——排除"仓库天然比住宅高"的干扰；系数差 ≥0.2 的 domain 必须体现方向 |
| `network_connected` | `arterial`+`local`+`quay` 构成单一连通分量（铁路单独成网，否则真实断头会被掩盖） |
| `rail_connected` | 恰好一条走行线，两端出图，专用线与它同属一个分量 |
| `bridge_over_water` | 每座桥的中点落在所跨水道的走廊内 |
| `sites_present` / `works_present` | 简报要求的每一类都达到要求数量（线性工程与船舶按走廊/泊位计） |
| `envelope_in_catalogue` | 每个包络的面积与高度落在目录区间内 |
| `envelopes_disjoint` | 任意两个包络不重叠 |
| `site_on_buildable` | 场址中心不在水面或保留区 |
| `needs_road` / `needs_water` / `needs_coast` / `needs_rail` / `needs_centre` | 场址到街道 ≤80 m、到水 ≤60 m（`water`）或 ≤120 m（`coast`，即"临水一排"）、到铁路 ≤150 m、到中心 ≤0.4×边长 |
| `adjacency` | 有邻近要求的场址距其伙伴 ≤220 m |
| `arterial_headings` | 干道方向中至少两条偏离 0°/90° 超过 8° |
| `work_length` / `work_on_water` | 线性工程长度落在目录区间（可在上限内截取）；码头与岸壁贴水；**船舶必须在水里** |

## 5. 实测（seed 4、512 m，四者全部 `pass`）

| 背景 | 街区 | 归属 | 干道长 | 桥 | 场址（已实现/未实现） | 走廊 |
|---|---|---|---|---|---|---|
| 魔法城邦 | 40（civic 6 / market 7 / residential 17 / craft 5 / green 5） | 城堡 9 / 行会区 12 / 外城 19 | 416 m | 16 | 35（32 / 3） | 1（城墙） |
| 现代都市 | 40（civic 6 / market 7 / residential 17 / industrial 5 / green 5） | 核心区 10 / 滨河 8 / 外围 22 | 438 m | 15 | 26（18 / 8） | 1（地铁） |
| 工业园 | 20（industrial 10 / market 2 / residential 5 / green 3） | 厂区 5 / 货场 7 / 住区 8 | 529 m | 6 | 13（4 / 9） | 1（铁路） |
| 港口 | 25（harbour 10 / market 4 / residential 8 / green 3） | 港务局 9 / 码头带 3 / 城区 13 | 525 m | 8 | 13（6 / 7） | 5（突堤、岸壁、船坞、灯塔、海关、货轮） |

干道方向实测（去重后）：魔法城邦 `[10.7°, 20.5°, 29.0°, 55.6°, 67.6°, 90.0°, 160.2°, 172.5°, 179.4°]`——不再只有 0°/90°。

## 6. 命令行

```powershell
$env:PYTHONPATH = 'src'
python tools/plan_districts.py --prompt "海运港口，码头货轮和仓库" --seed 4
python tools/plan_districts.py --setting arcane_medieval --seed 4 --output artifacts/arcane-districts.json
```

输出一张街区图（`C/M/r/w/g/I/H` 为用途、`*` 为已定场址、`#` 为干道）加统计与校验；退出码 0 表示通过。

## 7. 尚未做（如实记录）

- **街区是矩形**：`block` 用 `[x0,y0,x1,y1]`，因此街区边界仍平行于图轴。干道是多段折线（非正交），但**本地街网仍是正交的**——用户提到的"非正交路网"只完成了一半，需要不规则街区（多边形分割）才能做完整。
- 道路只是骨架几何：没有车道数、单向、交叉口渠化或交通仿真。
- 选址只保证"有包络且满足场址要求"，不保证包络内部的建筑（017 的工作）一定能排进去。
- 未与 006 的 WIR 实体对接：本阶段产物是独立数据，写入 WIR 属于 018。
