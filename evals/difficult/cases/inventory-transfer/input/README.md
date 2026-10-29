# 库房调拨服务材料包

本包全部为评测合成材料。源码用于说明一个服务层实现，报告为人工构造的测试记录；它们均不是本轮执行产生的结果。

当前材料基线为 `transfer-core 2.2`，以 `config.json`、`schema.sql` 和 `src/` 为当前实现。程序通过 Python 标准库操作 SQLite，调用方直接调用服务方法；本包没有网页、HTTP 层、完整身份认证或生产部署材料。

`thesis/positioning.md` 保存已确认的写作范围，`thesis/chapter-5.md` 是待审原稿，P 编号只用于定位。`reports/current-2.2.json` 对应当前基线，`reports/archive-1.4.json` 是保留的旧批次记录。报告中的每个数值应连同版本、批次、单位和状态理解。

输入索引：

- `config.json`：数量换算配置。
- `schema.sql`：表和约束定义。
- `src/service.py`：调拨创建、到货确认及业务拒绝条件。
- `src/repository.py`：事务边界和数据库读写。
- `reports/`：两份不同基线的合成记录。
- `thesis/`：已有定位及原稿。
