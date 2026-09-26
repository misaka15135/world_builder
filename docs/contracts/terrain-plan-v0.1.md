# 地形方案 0.1

版本：0.1.0。日期：2026-09-26。实现：`src/world_builder/planning/terrain.py`、`settings/*/terrain.json`、`tools/plan_terrain.py`。状态：**离线规则路径已实现并测试；它不是水文或工程地质模型。**

本文是流水线阶段 B（[014](../../work_order/014_terrain_plan.md)）的合同。背景见 [04_scene_pipeline.md](../04_scene_pipeline.md)，简报与目录见 [scene-brief-v0.1.md](scene-brief-v0.1.md)。

## 1. 它替掉了什么

旧路径的地形是解析函数 `height()`（一个正弦项加按 x 的线性渐变）加**城市正中 8 m 宽的直条河**：没有河网、没有丘陵、没有坡度统计，也没有"保留区"。本阶段用 **`terrain.json`（可执行要求）+ `TerrainPlan`（可采样数据）** 取代它。

## 2. `terrain.json`

```json
{
  "terrain_version": "0.1.0",
  "setting": "arcane_medieval",
  "relief": {"min_m": 0, "max_m": 26, "roughness": "rolling", "tilt": true},
  "water": {"kind": "river", "channel_count": [2, 4], "width_m": [8, 20], "fraction": [0.03, 0.16]},
  "slope": {"max_deg": 30, "mean_deg": [1.0, 12.0]},
  "reserved": {"steep_deg": 34, "water_buffer_m": 6}
}
```

- `relief.roughness` ∈ `flat` / `rolling` / `hilly`，决定起伏波长与占整体高度的比例。
- `water.kind` ∈ `river`（主河 + 支流）/ `canal`（顺直水道）/ `coast`（海岸线 + 航道）。**没有单独的 `coast` 布尔字段**：海岸线就是 `kind: "coast"` 的含义，同一事实写两遍只会互相矛盾。
- `slope.mean_deg` 不得超过 `slope.max_deg`；`reserved` 定义"陡坡"和"临水缓冲"的阈值，用于生成保留区。

规范（`setting.json` 里的 `terrain_preferences`）只是给 014 的**描述性偏好**；数字要求在本文件里，由 Schema 校验。

## 3. `TerrainPlan` 的产物

| 字段 | 含义 |
|---|---|
| `heights_m` | 采样网格（`spacing_m` 米步长，`region_m/spacing+1` 见方）；默认 4 m，与源端高程资源一致 |
| `channels[]` | 水道 / 岸线折线：`id`、`kind`、`width_m`、`points` |
| `water_level_m` | 只有 `kind: "coast"` 时有值；水面按高程分位数取，使水域占比落在声明区间 |
| `reserved[][]` | 保留区掩码：水面、超陡坡、临水缓冲带 |
| `stats` | 实测统计：高程范围、坡度均值/最大值、水域占比、水道数与总长、保留区占比 |

查询接口：`height_at`（双线性）、`water_at`、`slope_deg`、`distance_to_water_m`、`buildable_at`（0—1）。016 选址靠 `buildable_at` 与 `distance_to_water_m` 满足目录里的 `needs: water/coast`。

## 4. 生成模型与它的边界

地形是**一条区域斜坡 + 平行于排水方向的皱褶 + 有界的顺坡波纹**，并在水道附近把皱褶**平滑衰减到零**（河谷底平坦）。这不是装饰，而是为了满足"水必须能流到边界"这条硬要求：

- 斜坡给出确定的排水方向，所以水道自然出图、自然下降，不需要"从山上切一条沟"；
- 皱褶平行于排水方向，因此沿水道的下降不会被横向起伏抵消；
- 河谷底衰减到零，使蜿蜒的河道仍然保持下降，而两岸的丘陵留在远处。

**边界**：这不模拟水文过程，也不做工程地质结论；它是一套可校验的合成地形。真正的排水求解器是后续可以替换的升级项，而不是本阶段的声明。

## 5. 独立校验（`terrain.*`）

校验器**只看成品数据**，不看生成器中间状态：

| 规则 | 判据 |
|---|---|
| `terrain.relief` | 实测高程范围落在 `relief` 内（容差 0.5 m） |
| `terrain.slope_max` / `terrain.slope_mean` | 实测坡度不超过 `slope` 声明 |
| `terrain.water_fraction` | 实测水域占比落在 `water.fraction` 内 |
| `terrain.channel_count` | 水道数量落在 `water.channel_count` 内 |
| `terrain.width` | 每条水道宽度落在 `water.width_m` 内 |
| `terrain.coast` | 有岸线 ⟺ `kind: "coast"` |
| `terrain.flow_downhill` | 沿水道**存储的河床格子**高程单调不增，且总落差 > 0 |
| `terrain.water_in_valley` | 每个河床点相对其**横向**地面有更高的岸（平均值即"沟深"） |
| `terrain.water_connected` | 每条水道至少一端落在区域边界上 |

两条规则都有踩过的坑，写在代码注释里：`flow_downhill` 曾在**航道沿网格轴**时误报，因为采样的相邻格子同时是前一个和后一个河道格子；`water_in_valley` 同理，所以现在改成**垂直于流向**取样。

## 6. 实测（seed 4、512 m、8 m 网格；四者全部 `pass`）

| 背景 | 高程范围 m | 平均/最大坡度 | 水域占比 | 水道数 | 水道总长 m | 保留区 | 水系 |
|---|---|---|---|---|---|---|---|
| `arcane_medieval` | 0—26 | 4.13° / 20.51° | 7.8% | 4 | 1600.9 | 7.1% | 主河 + 3 支流 |
| `modern_metropolis` | 0—8 | 1.03° / 4.13° | 8.1% | 3 | 1016.3 | 6.0% | 运河 + 2 支渠 |
| `industrial_park` | 0—5 | 0.78° / 2.66° | 5.2% | 2 | 762.9 | 3.4% | 运河 + 1 支渠 |
| `harbour` | 0—12 | 1.46° / 3.48° | 42.5% | 1 | 2256.5 | 44.4% | 海岸线 + 航道 |

128×128 网格（`spacing_m = 4`，与源端高程资源同规格）实测同样 `pass`：水域 7.7%、4 条水道、序列化约 179 KB。

## 7. 命令行

```powershell
$env:PYTHONPATH = 'src'
python tools/plan_terrain.py --prompt "河谷里的魔法城邦，要有城堡" --seed 4
python tools/plan_terrain.py --setting harbour --seed 4 --spacing-m 4 --output artifacts/harbour-terrain.json
```

输出一张 ASCII 地形图（`~` 水、`^` 保留区、字符表示高程）加统计与校验结果；`--output` 写出完整 `TerrainPlan` JSON。退出码 0 表示校验通过。

## 8. 尚未做

- 不与 006 的高程资源对接：`TerrainPlan` 现在是独立产物，把它写进 WIR 的 `terrain`/`river` 实体属于 018（装配）与 006 的资源格式衔接。
- 不做湖泊、三角洲、潮汐、河漫滩沉积等更细的地貌；`hilly` 目前只在高度与波长上区别于 `rolling`。
- 不保证"道路/桥梁正确跨越"：那需要 016 的骨架，尚未实现。
