# WIR SQLite 存储

当前用于 Agent 主线的 WIR 存档；源世界及派生文件的关系见 [项目基线](../docs/00_project_baseline.md)、[WIR 契约](../docs/contracts/wir-v0.1.md) 和 [打包 ADR](../docs/adr/0001-wir-authority-and-packaging.md)。实现入口为 [Repository](../src/world_builder/storage/repository.py)。

`migrations/0001_initial.sql` 定义 WIR 0.1 的权威记录与修订结构。业务记录以经过 Schema 和语义校验的规范 JSON 保存，同时抽取身份、类型、父对象和包围盒用于查询。

迁移只追加新文件，禁止修改已经发布的迁移。数据库初始化和写入必须在事务中执行；应用负责先发布不可变资源，再提交引用。R*Tree 中的包围盒只用于候选查询，不能代替精确几何判断。

已有修订结构不代表 Agent 已实现同一世界上的持续编辑。目前生成后查看与回放只读；稳定世界/对象身份及依赖记录见 [032](../work_order/032_world_revision_identity.md)，锁、局部再生成和撤销/重做见 [033](../work_order/033_scoped_scene_revision.md)，均为后续任务。本次文档对齐不改变迁移或数据格式。
