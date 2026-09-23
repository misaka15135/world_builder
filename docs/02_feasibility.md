# 可行性调研与路线选择

日期及来源访问日期：2026-09-21。方法：阅读论文、标准与官方/维护方资料；未安装或复现相关系统，未运行 Unity、Minecraft 或 BIM 软件。

## 1. 结论与证据等级

**在有限规模、有限资产和明确平台版本下，首版具有工程可行性；完整的大世界与工程用途需要分阶段建设。** 这是综合既有能力和本项目资源作出的设计判断，不是端到端性能验证结论。

论文已经分别展示了自然语言室内布局、程序化自然环境、道路/地块生成和受约束室内生成。标准和工具也提供三维资产、方块区域及建筑构件的交换基础。本项目真正需要研发的是统一的语义源数据、跨层约束协议、修改传播、双目标编译和可验证的用户流程。

详细原始证据见 [生成调研](research/002_generation_evidence.md) 和 [元表示/导出调研](research/003_representation_evidence.md)。它们区分了文献事实、项目设计判断、访问失败后的引用范围和待验证事项。

## 2. 已有研究能支持什么

| 研究方向 | 一手证据 | 对本项目的启示 | 不能据此声称的能力 |
|---|---|---|---|
| 语言驱动室内场景 | [Holodeck 作者论文](https://arxiv.org/html/2312.09067v2) | 用语言模型产生对象与关系，再检索资产和求解布局 | 任意城邦、完整室内结构或真实工程自动成立 |
| 多阶段室内生成 | [ProcTHOR 原论文](https://proceedings.neurips.cc/paper_files/paper/2022/file/27c546ab1e4f1d7d638e6a8dfbad9a07-Paper-Conference.pdf) | 平面、门、物体和组合分别生成，保留语义 | 大量小场景等于一个无限大世界 |
| 程序化自然内容 | [Infinigen Nature](https://arxiv.org/abs/2306.09310v2) | 参数化地形/自然资产可减少逐对象模型调用 | 普通电脑可实时运行完整高质量管线 |
| 约束驱动室内生成 | [Infinigen Indoors](https://arxiv.org/html/2406.11824v1) | 用约束组织平面、楼梯占位与物体放置 | 启发式搜索保证最优，或布局满足施工要求 |
| 城市道路与地块 | [Procedural Modeling of Cities 原论文](https://people.eecs.berkeley.edu/~sequin/CS285/PAPERS/Parish_Muller01.pdf) | 将全局意图和局部几何约束分开，逐步生成道路/地块 | 同时解决详细建筑功能与所有室内 |
| 地形与水系耦合 | [地形生成论文作者页](https://perso.liris.cnrs.fr/apeytavi/website/publication/hal-01262376/) | 河网和高程应联合处理 | 本轮已复现算法或证明工程水文精度；此项仅核实作者摘要 |

上述工作可借鉴算法与接口设计，不应未经许可、依赖和性能检查就把它们全部嵌入产品。[Infinigen 官方资源配置说明](https://infinigen.cs.princeton.edu/docs/latest/ConfiguringInfinigen.html)也支持先区分交互粗预览与离线细节生成，再测量资源开销。

## 3. 技术路线比较

以下比较属于面向已确认资源的工程判断。

| 路线 | 优点 | 主要不足 | 决策 |
|---|---|---|---|
| 从零训练端到端大模型 | 理论上可统一学习复杂内容规律 | 数据、算力、结构化监督与可编辑性验证成本高；缺乏本项目训练数据 | 不作为首版路径 |
| 让 LLM 输出全部几何/方块坐标 | 实现演示入口直观 | 长输出成本高，数值/拓扑错误多，难以复现和局部修复 | 仅限小型意图/关系提案 |
| 纯程序化规则与模板 | 可控、易复现、资源可预测 | 开放语言和风格变化受规则覆盖限制 | 作为几何与布局基础 |
| 端到端图像/视频场景生成 | 可快速展示视觉概念 | 视觉结果不自动提供房间、构件、碰撞和稳定可编辑实体 | 可作参考图，不作权威源数据 |
| LLM + 程序化 + 约束 + WIR | 分开处理语言理解、几何和一致性；便于局部修改 | 集成和数据契约工作量大，需要持续验证 | 推荐路线 |

引入模型训练的条件应是：已有稳定数据契约、足量授权训练数据、可度量失败类型，以及现有模型/规则确实无法以合理成本解决的问题。例如以后学习室内布局候选排序；当前无需把该研究提前成项目依赖。

## 4. 通用元形式的可行性与边界

通用源数据可行，所有输出完全无损互转不可作为设计前提。不同目标分别保留连续几何、游戏实体、体素状态或建筑构件语义。

| 候选 | 适合承担的职责 | 不宜直接承担的全部职责 |
|---|---|---|
| [OpenUSD](https://openusd.org/24.08/intro.html) | 资产组合、引用、变体、分层覆盖、按需 payload | 不会自动定义世界生成算法、领域约束与项目事务 |
| [glTF 2.0](https://registry.khronos.org/glTF/specs/2.0/glTF-2.0.html) | 运行时几何、材质、节点与动画交付 | 不自动提供道路/房间关系图、规划配方与工程构件知识 |
| [IFC](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcproductextension/lexical/ifcspace.htm) | 建筑空间和构件的语义交换 | 不是魔法世界的通用生成控制协议，也不能补出缺失工程输入 |
| 自定义 WIR + 标准几何资源 | 持有实体身份、语义、约束、生成来源与版本 | 需自行维护 Schema、迁移、适配能力和验证器 |

推荐新建领域层 WIR，复用几何格式与数据库。首版不开发新的三角网格编码，也不强制以 OpenUSD 替代所有存储。格式之外还必须有执行和验证语义，否则只是把自由文本装进 JSON。

## 5. 三条导出路线的成熟度

**Unity：已有明确资产导入路径，地图级功能需要补齐。** 官方 glTFast 支持 Editor/运行时导入，Editor 可产生 prefab；本项目还要实现分块清单、对象映射、碰撞、材质和约定的导航设置，再进行实际漫游验收。[glTFast 官方文档](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.19/manual/index.html)、[Editor Import](https://docs.unity3d.com/Packages/com.unity.cloud.gltfast@6.19/manual/ImportEditor.html)

**Minecraft：区域粘贴路径较清晰，方块化是语义重建问题。** Sponge v3 与 WorldEdit 提供区域交换基础，但 `.schem` 是区域剪贴板；完整世界涉及元数据和原生区块等另一组要求。首版采用固定 Java/WorldEdit 组合，后续独立验收世界目录。门洞、楼梯和通路必须在方块化后再检查。[Sponge v3](https://github.com/SpongePowered/Schematic-Specification/blob/master/versions/schematic-3.md)、[WorldEdit Clipboard](https://worldedit.enginehub.org/en/latest/usage/clipboard/)、[MCA Selector 维护方资料](https://github.com/Querz/mcaselector/wiki/Chunk-Filter)

**工程模型：可先验证构件语义，不能直接承诺可施工。** IFC/IfcOpenShell 为构件和空间模型提供基础；建筑外壳网格本身缺少墙体材料、空间关系与专业设计参数。先交付有明确模型用途的概念 IFC，再按实际工程任务增补专业输入和验证。[IfcWall 定义](https://standards.buildingsmart.org/IFC/RELEASE/IFC4/ADD2_TC1/HTML/schema/ifcsharedbldgelements/lexical/ifcwall.htm)、[IfcOpenShell 几何创建](https://docs.ifcopenshell.org/ifcopenshell-python/geometry_creation.html)

## 6. 本地查看、存储与约束工具

- Three.js 已提供 [glTF 加载](https://threejs.org/docs/pages/GLTFLoader.html)、[实例化](https://threejs.org/docs/pages/InstancedMesh.html)和 [LOD](https://threejs.org/docs/pages/LOD.html)。本项目还需实现分块调度、选中语义、编辑事务和失效更新。是否达到目标帧率必须实测。
- SQLite 的 [R*Tree](https://www.sqlite.org/rtree.html)适合空间候选检索。源几何仍单独保留足够精度，精确碰撞不由包围盒索引代替。
- [OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver)可处理整数约束问题，适合离散布局中的部分任务；连续曲线和实体运算仍需几何算法。超时不能当作无解证明。
- [Tauri](https://tauri.app/concept/process-model/)可作为后续桌面封装候选。复用系统 WebView 不会消除模型资产、Python 服务和平台兼容成本，首版先验证本地浏览器流程。

## 7. 需要先做的工程实验

1. 用手工 WIR 构造河桥、两层房屋和家具，验证包含树、连接关系、单位与目标转换。
2. 构造楼梯放不下、锁定对象与河道冲突、求解超时等案例，验证失败分类和有限回溯。
3. 修改椅子、建筑轮廓和河道，测量依赖传播范围，检查无关实体保持稳定。
4. 在同一源修订上进行 Unity 和 Minecraft 样件导出，实际检查朝向、比例与通行；随后再扩大为完整城邦。
5. 固定普通电脑基准和资产预算，记录帧时间、工作集、生成分段耗时、API 用量及取消恢复。

上述实验由 005—009 工单落实。数据契约先行，早期适配器样件可与生成器并行试验；完整城邦联调放在相应阶段末尾。

## 8. 不确定性与建议

最高风险来自跨层约束、语义编辑、方块化功能保持和资产覆盖，未必来自语言理解本身。小团队应先用有限规则和少量资产实现一个完整闭环，再依据量化结果增加风格、规模和目标。

当前能确定的是架构方向和可验证路径；不能确定的是实际帧率、生成时长、费用、特定软件版本互操作性与最终审美质量。正式方案中的规模、资源目标和 8—14 人周 MVP 工作量均为待验证的初始估算。
