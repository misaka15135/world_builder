# 世界元表示与跨目标导出调研

- 对应工单：003。
- 调研日期：2026-09-21。
- 范围：个人或小团队、普通电脑运行、允许调用云端模型 API；首版验证可编辑魔法城邦及 Unity、Minecraft 导出。
- 状态：方案研究。未安装、运行或验证本文所述导出链路；以下性能和互操作性要求均属于后续验收项。
- 证据标识：**文献证据**表示来源明确支持的事实；**设计判断**表示面向本项目的选择；**待验证**表示尚未通过工程试验。

## 1. 结论

建议建立项目自己的 World Intermediate Representation（WIR，世界中间表示），以类型化语义、空间关系、生成配方和约束为权威源数据，使用现有标准存放或发布几何资产。WIR 不是另造一种网格格式，也不应声称能使全部目标无损互转。

推荐路线为：`自然语言需求 → 语义与约束 WIR → 目标专用编译 → GLB / Unity 场景 / Minecraft 区域 / IFC 概念模型`。原始意图、被接受的规划结果、人工覆盖、生成版本和导出损失留在 WIR；导出文件是可重建的派生产物。

与正式方案统一，首版以 **SQLite 中的语义/修订记录和内容寻址的不可变资源文件** 为权威数据，`.worldpkg` 中的版本化 JSONL 快照承担便携交换职责。OpenUSD 适合作为未来复杂资产组合与 DCC 交换桥接；不要求普通电脑的首版编辑器同时承担完整 USD 运行环境。该判断来自项目规模与迭代成本，不能据此断言 OpenUSD 性能不足。

## 2. 一手资料与适用边界

下列来源均于 **2026-09-21** 访问。规范版本与资料版本分别列出，资料存在不代表本项目已完成集成。

| 编号 | 来源及版本 | 文献证据 | 本项目的适用边界 |
|---|---|---|---|
| R1 | [OpenUSD Introduction，24.08 固定版文档](https://openusd.org/24.08/intro.html) | 支持 layer、reference、payload、variant 和非破坏性覆盖；payload 可按需加载。USD 支持属性、关系与自定义 schema | 可以组织几何和资产组合；应用级规划约束、重生成协议和目标映射仍需定义。稳定对象 ID 不能依赖会改变的层级路径 |
| R2 | [Khronos glTF 2.0 规范](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html) | 面向运行时资产发布，描述节点、网格、材质、动画等；核心节点为严格树；长度单位为米，采用右手系、Y 向上 | 可做预览与几何交付。应用约束和关系图即使通过 extras/extensions 携带，也不自动获得第三方软件理解或执行 |
| R3 | [Unity glTFast 6.19.0 文档](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.19/manual/index.html) | Unity 官方包提供 Editor 与运行时 glTF 导入/导出，并列出渲染管线和扩展支持 | 证明存在导入路径；具体 Unity Editor、包版本、渲染管线与所用扩展仍需联合测试 |
| R4 | [Unity glTFast 6.19.0 Editor Import](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.19/manual/ImportEditor.html) | Assets 中的 glTF/GLB 可导入原生 prefab；通过 ScriptedImporter 处理文件扩展名 | 不等于已经生成可游玩的地图。碰撞、导航、灯光和业务组件应由项目的 Unity 适配器显式构造并验证 |
| R5 | [Sponge Schematic v3 规范](https://github.com/SpongePowered/Schematic-Specification/blob/master/versions/schematic-3.md) | 描述有限区域，包含尺寸、Offset、DataVersion、方块状态 palette、方块实体、实体和生物群系；底层为 NBT；方块数据按区域索引 | 是 Minecraft 区域交换格式，不是完整世界存档。未知方块状态属性和目标注册表差异可能导致错误 |
| R6 | [EngineHub WorldEdit Clipboard，7.4 文档](https://worldedit.enginehub.org/en/latest/usage/clipboard/) | 支持区域复制、粘贴和 schematic 保存/加载；现代 Sponge 使用 `.schem`，历史 MCEdit `.schematic` 通过兼容层读取 | 首版可通过 WorldEdit 导入区域。粘贴原点、空气、实体、生物群系选项必须纳入验收 |
| R7 | [MCA Selector 维护方：Chunk Filter](https://github.com/Querz/mcaselector/wiki/Chunk-Filter) | 区块操作区分数据版本；导出区块可能创建 `region`、`poi`、`entities` 目录 | 佐证原生世界导出涉及多类区块数据，不能把 `.schem` 改后缀当作 `.mca`。本来源是工具维护方资料，不是 Mojang 全量格式规范 |
| R8 | [buildingSMART IFC4 ADD2 TC1：IfcSpace](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcproductextension/lexical/ifcspace.htm) | IFC 空间具有空间结构和关系定义；包含空间边界相关关系 | 房间应保留空间语义，不能只保存可见表面网格 |
| R9 | [buildingSMART IFC4 ADD2 TC1：IfcWall](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcsharedbldgelements/lexical/ifcwall.htm) | 墙构件有类型、材料及几何表达概念 | 支持构件语义映射；一个任意建筑外壳网格并不能提供缺失的墙体与构造信息 |
| R10 | [IfcOpenShell 0.8.5：Geometry creation](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html) | 可通过代码建立构件几何；一个构件可有多种表达；项目单位须明确，类型和材料定义影响几何 | 可用作 IFC 导出实现工具；调用成功不能替代模型语义检查、目标软件检查和实际工程审查 |

## 3. 为什么需要项目级 WIR

### 3.1 不同格式解决的是不同问题

- OpenUSD 提供强大的资产组合和场景描述机制，可承载自定义世界语义，但这些语义及其执行逻辑仍由项目定义。[R1](https://openusd.org/24.08/intro.html)
- glTF 聚焦运行时交付，核心节点树并不直接表达道路连通、房间相邻、河流上下游、生成依赖等多种关系；这些关系应保存在项目语义层。[R2](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html)
- Minecraft 接收方块及其状态，连续曲面、任意角度家具和真实尺寸墙体需要量化与替代。[R5](https://github.com/SpongePowered/Schematic-Specification/blob/master/versions/schematic-3.md)
- IFC 表达建筑空间、构件和相关信息；工程语义不应在最终导出时从一张渲染网格中猜测。[R8](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcproductextension/lexical/ifcspace.htm)、[R9](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcsharedbldgelements/lexical/ifcwall.htm)

**设计判断：**真正需要统一的是世界对象及其意图、约束和身份。地形、建筑、植被和家具可以各自采用合适的几何表示，而不必强行转成同一种几何后再开始编辑。

### 3.2 建议保留的语义与几何

| 内容 | 权威表达 | 派生表达 |
|---|---|---|
| 地区及地形 | 边界、地形场/高度场参数、河网、地表分类、保护区 | 预览网格、纹理、Minecraft 地表方块 |
| 道路与桥梁 | 中心线、宽度、交叉口、桥跨、标高和连通关系 | 路面网格、碰撞、方块道路 |
| 地块与建筑 | 地块多边形、占地轮廓、楼层、风格、入口、建筑规则 | 外壳网格、目标 prefab |
| 房间与结构元素 | 房间边界、墙体中心/基线与厚度、楼板、门窗洞口、楼梯路径和净空 | 室内几何、Minecraft 量化结构、可映射 IFC 构件 |
| 家具与植被 | 资产引用、尺寸、实例变换、功能区和接触/支撑关系 | 实例化网格、目标替代资产 |
| 魔法元素 | 语义标签、视觉需求、允许违反的物理约束、目标实现策略 | Unity 特效/灯光、Minecraft 发光方块或装饰；不支持时告警 |

设计时区分 `authoritative` 与 `derived`。例如规则建筑的墙体参数为权威数据，网格是派生缓存；导入雕塑则可把原始网格指定为权威数据，并明确它缺乏墙体/房间语义。不得维护两个互不校验的权威几何副本。

高度场只能表示单值表面。洞穴、悬挑和浮岛应采用独立体积/网格资产及明确的碰撞和导出策略。首版不必实现通用 SDF 或全世界体素存储。

## 4. WIR 最小合同建议

本节是设计建议，建议版本号从 `0.1.0` 开始，最终字段由后续 schema 工单冻结。

### 4.1 数据类别

| 类别 | 必要字段或能力 | 目的 |
|---|---|---|
| 世界清单 | schema 版本、世界 ID、修订号、单位、坐标系、范围、全局 seed、资源清单 | 决定如何正确解释整个项目 |
| 对象 | 稳定 ID、类型、父对象、所属分块、包围盒、局部变换、状态 | 身份独立于名字和树路径；区分已规划、已求解和已物化 |
| 关系 | contains、adjacent、connects、supports、drains_to 等类型化边 | 区分包含树与跨层关系图 |
| 生成配方 | 生成器 ID/版本、规范化参数、已接受规划结果、局部 seed、输入哈希 | 支持局部重建和来源追溯 |
| 约束 | 对象集合、谓词/参数、单位、hard/soft、容差、优先级、来源 | 让生成器和验证器共享同一需求 |
| 资产 | 内容哈希、相对 URI、媒体类型、单位/轴向、许可来源、LOD、碰撞引用 | 避免资产丢失和跨工具尺寸错乱 |
| 编辑 | base revision、操作 ID、对象 ID、操作内容、锁定字段、执行者 | 维护人工修改、撤销和冲突检测 |
| 导出配置 | 平台、版本组合、能力集合、缩放、原点、材料与语义映射版本 | 避免导出结果取决于隐含环境 |
| 导出报告 | 对象 ID 到目标对象的映射、保留/近似/缺失项、误差、版本、验证结果 | 让用户知道具体失去了什么 |

随机种子不能单独保证云端模型调用可复现。须保存被接受的结构化规划、模型及提示版本、输入资产版本与生成器版本；尽可能使几何阶段由确定性算法重建。重试、并行顺序与局部生成应采用按稳定对象 ID 派生的 seed，避免编辑一个房间改变整座城市。

### 4.2 坐标、单位与空间分块

建议 WIR 使用米、弧度、右手 Z-up：X 向东、Y 向北、Z 向上；全局坐标使用 float64，渲染几何使用分块局部原点及 float32。此处是项目约定，不代表目标平台默认约定。

导出器必须执行显式坐标变换，连同旋转、法线、三角形朝向、包围盒和碰撞一起转换。glTF 使用米和 Y-up；Unity 导入库可能已承担部分坐标转换，必须用带 X/Y/Z 标记的非对称测试件验证，避免重复翻轴。Minecraft 另有整数格点、方块朝向和世界原点，需要独立映射。[glTF 单位与坐标规范](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html#coordinate-system-and-units)

分块是加载与存储索引，语义对象不必被强行切断。跨边界道路、河流和建筑应有一个权威对象及各分块引用；重复几何缓存可以存在，重复对象身份不应存在。相邻分块共享边界样本或边界约束，避免独立生成裂缝。

### 4.3 文件组织与事务

运行期使用 SQLite 和不可变资源库；便携 `.worldpkg` 的逻辑分区包括 `manifest`、`entities`、`relations`、`constraints`、`recipes`、`assets`、`tiles`、`edits`、`exports`。具体后缀与分片粒度在原型中确定。

- 对外语义合同采用 JSON Schema，便携快照使用 JSONL；大数组、网格与贴图用二进制资源，禁止将全部数据塞入一个巨大 JSON。
- 本方案选择 SQLite 保存权威语义、关系、修订与事务数据；JSONL 是导出快照，不能作为第二套可独立修改的主数据。纯 JSON 加可重建索引是曾评估的简化选项，不作为本方案默认。
- 资源先写临时文件、计算哈希并发布至不可变路径，再在数据库事务中提交引用和修订；中断时保留上一有效修订，孤立资源延后回收。便携包完整校验后原子替换，实际文件系统能力须验证。
- 单写者队列比首版直接引入分布式协同更可控；跨对象操作需事务边界，避免撤销或并发产生半个更新。
- 对象修订与依赖图驱动失效：上游变化只使相关结果变脏，保留锁定字段；发现硬约束冲突时报告冲突，不能悄悄覆盖用户编辑。
- 图形界面上的拖动、替换材质、移动入口应产生语义操作；自由顶点编辑若破坏参数关系，须显式转为网格覆盖模式，并提示相关导出能力下降。

## 5. 导出能力矩阵与边界

| 源信息 | Unity 首版 | Minecraft 首版 | IFC 后续阶段 |
|---|---|---|---|
| 地形和建筑可见几何 | 分块 GLB + 导入适配器，目标为可打开并继续编辑的场景 | 目标版本 palette 的方块区域；轮廓发生量化 | 场地和建筑概念几何，表达按工具支持确定 |
| 房间与构件语义 | 自定义组件或 sidecar；非 Unity 标准语义 | 主要留在 WIR 和映射报告，游戏不原生理解全部关系 | 显式映射空间、楼层、墙、板、门窗等 |
| PBR、发光和魔法特效 | 支持子集；复杂着色与行为需 Unity 专用实现 | 方块材质/发光属性或目标专用内容近似 | 通常只保留表面表现或自定义说明 |
| 碰撞与导航 | 由 WIR/简化形状构造 collider；导航另行烘焙 | 按游戏方块形状、状态和通行规则重新检查 | 不等同于游戏导航；工程分析另行处理 |
| 生成配方、约束与编辑历史 | 保存在源项目；可带摘要 | 保存在源项目 | 可带有限属性，不承诺跨软件执行 |
| 任意外部修改回写 | 首版不承诺通用自动回写 | 首版不承诺从方块反推参数建筑 | 首版不承诺任意 BIM 工具无损往返 |

### 5.1 Unity：几何导入和场景交付分两级验收

**文献证据：**glTFast 能将 GLB 导入 Unity prefab。[官方 Editor Import](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.19/manual/ImportEditor.html)

**设计判断：**首版输出包应包含分块 GLB、WIR 对象映射及 manifest，并提供 Unity Editor 导入脚本构造场景。若只交付 GLB，应命名为“Unity 可导入资产”，不能称为已经完成 Unity 地图。

实际地图验收至少包括：场景能打开，尺度与原点正确，材质引用有效，主要对象保有稳定 ID，基础碰撞有效，路线可行走，重复导入不会无限复制对象。Terrain、NavMesh、灯光烘焙、特效和交互逻辑属于显式能力，不由文件后缀保证。

性能策略优先资产复用、实例化、LOD 和分块。一个巨型 GLB 与无约束的每块砖一个 GameObject 均不应成为默认方案。具体包大小、帧率、导入时间属于待测指标。

### 5.2 Minecraft：量化编译，不是换容器

推荐首版选择 **Java Edition + 一个锁定的游戏版本 + 一个锁定的 WorldEdit 版本 + Sponge v3 `.schem`**。游戏版本及插件/加载器版本必须在兼容性试验后形成固定 profile；当前调研未声称某个版本组合已经通过验收。Bedrock 采用不同适配路线，不纳入同一个首版承诺。

体素编译器应从语义构件、体积与地形生成方块，同时处理墙厚、门宽、楼梯、屋顶、树冠、流体边界及方块朝向。仅对外表面着色采样会得到不可走、没有内饰或漏水的空壳。

`meters_per_block` 是显式参数。建议起始采用 1 米/方块；对门窗、楼梯、家具以目标专用规则重构。增大世界在 Minecraft 中的比例能保留更多细节，但方块数量和区域内存随三维尺度快速增长。细节小于目标分辨率时须选“放大、替换、合并、删除或失败”之一，并记录策略。

输出时检查 palette、DataVersion、尺寸、原点、目标维度高度范围和方块实体；生成后检查门是否可穿行、楼梯是否连通、光照需求、液体是否溢出、特殊方块是否依赖支撑。Sponge 的版本字段与 Minecraft 的 DataVersion 是不同概念。[Sponge v3 规范](https://github.com/SpongePowered/Schematic-Specification/blob/master/versions/schematic-3.md)

完整区域应按适当大小分片并附粘贴清单。一个 512 × 512 × 128 的区域含 33,554,432 个位置，这是尺寸乘积，尚不包括解析器对象、palette 与附属数据；不得用压缩后的磁盘大小估算峰值内存。

`.schem` 是区域剪贴板；`.mca` 是原生世界区域文件的一部分；完整可打开世界还涉及世界元数据、维度、区块状态和版本相关数据。后续整世界路线优先在临时目标版本世界中由游戏/受维护工具导入并保存，或通过另一个专门工单实现原生写入，不把当前 `.schem` 导出宣称为完整世界导出。[WorldEdit](https://worldedit.enginehub.org/en/latest/usage/clipboard/)、[MCA Selector 维护方](https://github.com/Querz/mcaselector/wiki/Chunk-Filter)

### 5.3 IFC：保留工程扩展路径，但按等级交付

建议区分三个成果等级：

1. 建筑概念几何：可以查看建筑形态和空间布局；不保证构件语义完整。
2. 语义 IFC 概念模型：具有项目、场地、建筑、楼层、空间和选定构件；单位、几何与关系通过声明的校验规则。
3. 可施工工程成果：需要项目地点、用途、法规定义、荷载、材料、结构和机电系统、专业计算、图纸与有资质的人员审查等独立工作。

第 2 级通过文件或 schema 校验不推出第 3 级成立。此处是产品范围划分，不是针对任何司法辖区的工程合规意见。

面向未来 IFC 的 WIR 应尽早保留墙体、楼板、洞口、空间、尺寸和构件类型。映射失败的雕塑、浮空建筑或纯网格资产应使用适当的代理表达并报告语义缺失，不能为了通过导出将所有对象虚构为墙体或宣称结构成立。

概念验证可选择 IFC4 ADD2 TC1 作为候选交换版本，用 IfcOpenShell 建模；具体 IFC 版本和目标 BIM 软件须通过样件验收后冻结。构件类型、材料层和空间边界的缺失应显式列出，不能由导出器编造专业参数。[IfcOpenShell Geometry creation](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html)

## 6. 导出报告必须回答的问题

每次导出产生机器可读报告及简洁摘要，至少记录：

- 输入世界修订、schema 版本、适配器版本、目标环境、坐标/单位变换与资产哈希。
- 对象 ID 到目标节点、方块范围或 IFC GlobalId 的映射。
- `preserved / approximated / omitted / unsupported / failed` 分类及对象级原因。
- 量化分辨率、边界误差、替换材料、删除细节、失效语义、性能预算超限。
- 导出前和导出后验证结果；“文件生成成功”“目标软件读取成功”“可游玩/可继续编辑”分别记录。

在预览器提供目标能力预检，例如显示“此楼梯在 1 米格点下不连通”。能从上游规划阶段感知目标限制时，应把它作为设计约束；多目标冲突无法同时满足时，保留源设计并生成各自的目标变体。

## 7. 主要风险及后续实验

| 风险 | 设计措施 | 必须执行的实验 |
|---|---|---|
| 自定义格式无限扩张 | 定义小型 schema、扩展命名空间、迁移协议；复用几何标准 | schema 迁移及旧世界读写样件 |
| 语义与网格不同步 | 单一权威表达、依赖哈希、缓存失效、人工覆盖记录 | 修改入口后局部重建，确认其他对象 ID 和编辑不变 |
| 云模型结果不可复现 | 保存已接受规划及版本，几何阶段确定化 | 相同计划/版本重建得到相同语义与几何摘要 |
| 轴向或单位错误 | 显式适配器及非对称测试件 | 两层建筑、斜屋顶、楼梯和朝向门跨 Unity/Minecraft 比对 |
| 体素化破坏功能 | 语义量化规则和目标空间验证 | 最小门宽、转角楼梯、桥、河岸和屋顶测试集 |
| 大区域内存失控 | 分块、资产复用、按需加载、分片导出 | 记录峰值 RSS、导出时长、磁盘量和取消恢复 |
| 不同软件保留能力不同 | 版本 profile 与损失报告 | 目标软件实际打开、保存、重开；不只检查文件语法 |
| IFC 外观被误认作工程正确 | 声明模型等级、保留缺失属性、专业验证另立工单 | IFC 独立查看器检查构件类别、层级、单位、几何和空间关系 |

建议后续按顺序实施：① WIR 最小 schema 与能力 profile；② 一个有两层、门窗、楼梯和家具的固定样件；③ Unity 与 Minecraft 双导出试验；④ 在验证过的表示上扩大到城邦；⑤ IFC 语义概念模型试验。整世界 `.mca`、外部编辑无损回写和多用户实时协作应分别立项，避免首版范围失控。

## 8. 本次研究的未决项

- Unity Editor、glTFast、渲染管线的精确兼容组合尚未实际安装验证。
- Minecraft Java、WorldEdit、加载器的精确版本组合和粘贴性能尚未验证。
- WIR 与 OpenUSD 的最终职责分界需要样件和资产规模数据；当前建议不将 USD 设为首版强依赖。
- 地形分辨率、最大地图规模、内饰比例、每块预算和导出误差阈值应由基准测试确定。
- IFC 接收软件、具体交换要求与目标司法辖区尚未定义，因此当前只能设计扩展路径。
