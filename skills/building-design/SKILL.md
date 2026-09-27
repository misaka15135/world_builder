---
name: building-design
description: Research, design, or review a stage E building for the world builder. Choose a historical or contemporary architectural precedent, turn its spatial logic into a buildable Minecraft and WIR concept, and check appearance and access without imposing one style on every type.
metadata:
  short-description: Evidence-based building design for stage E
---

# 阶段 E：建筑设计

适用：设计或评审 `settings/*/designs.json` 模板、`planning/designer.py` 的单栋方案、导出后的建筑观感。**先选功能、时代、地区、气候和场地，再选风格。** 不把“城堡”“中式”“现代”当成单一外观包，也不把视觉参考当成可施工的真实工程图。

## 按需要阅读

- 历史及地方建筑：读 [历史与地方风格卡](references/historic-and-vernacular.md)。覆盖中国院落、日本合掌造和城堡、欧洲木构/哥特/乔治时代建筑、西南亚与北非院落、印度寺庙、西非土构、普韦布洛土坯建筑。
- 近现代与基础设施：读 [近现代与工业风格卡](references/modern-and-industrial.md)。覆盖包豪斯、现代主义住宅、装饰艺术、高层、矿业厂区、铁路车站及当代 Minecraft 建造法。
- 具体功能与验收：读 [建筑类型与建造流程](references/programmes-and-workflow.md)。覆盖住宅、商铺、旅店、学校、医院、市政建筑、宗教建筑、城堡、车站、工坊/工厂等。

每张风格卡包含**可观察特征 → 可操作建造步骤 → 当前项目能力边界 → 一手来源**。来源描述的是特定地点或案例；把它转成项目模板属于**设计推断**。不能把某一案例扩展成整个文化的统一样式。

## 设计顺序

1. **定一句话主旨**：例如“沿街店面＋后院工坊的欧洲木构建筑”或“围绕庭院组织、朝内采光的北非住宅”；同时注明参考建筑、时代和来源。
2. **定场地与动线**：标注道路、入口、地形、水、邻栋、公共/私密边界。先画一层平面、庭院及竖向交通，再决定立面。大厅、厂房、车站等可用一个主要大空间；不要机械要求“每层两间房”。
3. **定可识别轮廓**：从街道高度和俯瞰两个距离看，屋顶线、塔楼/门楼、前后院或大跨屋架应能表达所选类型。体量个数由功能和先例决定；单体量也可优秀，例如合掌造的巨大坡屋顶、包豪斯的互锁方体。
4. **定立面节奏**：先定结构开间、入口和实墙/开口的重复关系，再补基座、檐口、窗框、扶壁、阳台等细节。装饰必须服务所选风格，避免把所有元素堆在一面墙上。
5. **定材质与光**：先试主材、结构材、屋面及一处强调色；近看检查纹理，远看检查明暗和主次。材质数量随建筑规模而变，不设“最多四种”的硬上限。[Minecraft 官方建造建议](https://www.minecraft.net/en-us/article/make-your-houses-better)强调立面深度、近色纹理和景观；[官方建造者访谈](https://www.minecraft.net/en-us/article/raeyzeus-top-5-building-tips)也区分小塔与大型建筑的调色规模。
6. **定可走通的空间**：画出从外部道路经门、通道、楼梯/坡道到每层主要用途空间的路径；房间用途、家具、采光与入口关系一致。多层楼的每一层都要有路径，不得只做通往二层的一段楼梯。
7. **做两次审视**：灰模先看比例、屋顶和负空间；落材后看街景和俯瞰，并实测入口与逐层通行。允许回到平面改动，不靠加随机装饰补救错误体量。

## 项目约束与证据口径

- 尺寸均以 **m** 表示；在 Minecraft 投影中会栅格化为方块。`BuildingDesign` 的轮廓、楼层、入口、房间、楼梯井、屋顶和场地包络是实际契约；设计时遵守 `docs/contracts/building-design-v0.1.md`。入口约 2.0 × 2.4 m、门垛约 1.0 m、墙角余量 0.3 m 是当前适配器的**具体目标约束**，不是古今建筑通用美学比例。3.0 m 层高、0.6 m 出檐、6—8 m 窗距可作为试画起点，不能跨风格强制；适配器已有低于 3.0 m 首层的门槛开洞策略。
- 当前可核对的源端规则包括 `design.outline`、`design.height`、`design.rooms_inside`、`design.stair_void`、`design.stair_fits_void`、`design.furniture`、`design.volumes_clear` 和 `target.building_entry`。这些只证明几何/放置条件，不证明建筑“好看”或真实可达。
- 现行几何以**轴对齐盒体、逐层退台、flat/gable/spire 屋顶和 compound 多体量**为主。城堡圆环由多边形墙段近似；没有通用圆柱、穹顶、真实曲面、拱、连续坡道、复杂悬挑、窗户或上述风格卡中的专用构件生成器。风格卡中的这些步骤是**待实现设计目标**，不能在工单里记作已实现。
- 在能力不够时保留建筑的**平面组织与轮廓特征**，并登记所需新几何词汇；不能只换方块颜色就宣称做出了某种地域风格。不得把历史建筑的示意做法用于真实施工或规范审查。

## 交付一栋设计时记录

`类型 / 时代与地区 / 先例链接 / 主旨 / 平面与逐层动线 / 轮廓与屋顶 / 街面节奏 / 材质与场地关系 / 已实现字段 / 缺失能力 / 灰模及目标截图 / 验证结果`。将**来源事实、设计判断、实际目标测试**分开写；感官评价可用同视角对照和明确的“轮廓/节奏/比例/细部”理由支持，不能填成自动校验通过。
