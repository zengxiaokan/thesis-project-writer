# 合成设备借还材料 R0

本文件为人工构造的教学输入，不是从真实项目提取的证据。以下 S1—S6 定义本例允许使用的实现事实；未列明的功能、测试结果及部署情况不补造。两份章节均基于本版本。

## S1：范围、入口与数据对象

合成模块使用 SQLite 保存设备当前状态和借用历史，对外提供三个服务函数：`borrow`、`return_loan`、`query_loans`。未提供前端页面、HTTP Controller 或网络协议。章节可说明服务函数及数据层机制，不能补出未给定的页面、路由或接口响应码。

借用人提交设备编号后发起借用登记；归还请求使用借用记录编号及设备归还去向。`borrower_id` 是传给服务的借用人标识，不是已核实的登录身份。本例不包含账号表、认证或资源归属校验。

数据结构的合成定义如下，**仅作材料，未执行**：

```sql
CREATE TABLE equipment (
    equipment_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('available', 'loaned', 'maintenance'))
);

CREATE TABLE loan (
    loan_id INTEGER PRIMARY KEY,
    equipment_id INTEGER NOT NULL REFERENCES equipment(equipment_id),
    borrower_id TEXT NOT NULL,
    borrowed_at TEXT NOT NULL,
    returned_at TEXT,
    return_status TEXT
        CHECK (return_status IS NULL OR return_status IN ('available', 'maintenance'))
);

CREATE UNIQUE INDEX one_open_loan_per_equipment
    ON loan(equipment_id)
    WHERE returned_at IS NULL;
```

`equipment` 保存设备当前状态；`loan` 保存每次借用关系及借还时间。`available` 表示可借，`loaned` 表示借出，`maintenance` 表示归还后进入维护状态。`returned_at IS NULL` 是查询和部分唯一索引所采用的未归还记录口径。已归还记录保留在 `loan` 中，不通过删除历史记录表达归还。

建表定义声明了 `loan.equipment_id` 的外键，但没有运行库检查或外键启用记录；只能描述声明，不声称运行时已验证外键约束生效。部分唯一索引限制的是同一设备的未归还记录，不限制该设备的全部历史记录数量，也不是对 `borrower_id` 设置唯一约束。

## S2：借用登记 `borrow(equipment_id, borrower_id, now)`

`now` 是服务本次取得并传入数据层的时间字符串，直接用于本次记录，不包含性能耗时含义。输入、处理顺序和结果约定为：

1. 将 `borrower_id` 去除首尾空白；结果为空时抛出 `InputError`，不开始数据库写入。
2. 执行 `BEGIN IMMEDIATE` 开始写事务，在该事务内按 `equipment_id` 查询设备。
3. 设备不存在时抛出 `NotFoundError`；状态不是 `available` 时抛出 `InvalidStateError`。两种情况均发生在插入借用记录之前，事务随后回滚。
4. 插入 `loan`：保存设备编号、规范化后的借用人标识及 `borrowed_at=now`，`returned_at` 和 `return_status` 均为 NULL。
5. 将对应 `equipment.status` 改为 `loaned`，提交事务，向调用方返回新 `loan_id`。
6. 若插入触发 `one_open_loan_per_equipment` 唯一约束，回滚并抛出 `ConflictError`；其他数据库读写错误回滚并抛出 `StorageError`。失败时本次借用记录与设备状态修改均不提交。

本例没有预约、队列、名额、借用时长上限或逾期处理规则。事务和唯一索引是合成实现的机制约定，不是已完成并发实测的结果。

## S3：设备归还 `return_loan(loan_id, disposition, now)`

`disposition` 表示归还去向，只接受 `available` 或 `maintenance`：

1. 其他去向先抛出 `InputError`，不开始数据库写入。
2. 执行 `BEGIN IMMEDIATE`，在事务内按 `loan_id` 查询借用记录。
3. 记录不存在时抛出 `NotFoundError`；`returned_at` 已非 NULL 时抛出 `AlreadyReturnedError`。两种情况都在本次写入前结束并回滚事务，不覆盖历史归还信息。
4. 将该条 `loan.returned_at` 设为 `now`、`loan.return_status` 设为 `disposition`，不修改原借用人和借用时间。
5. 将该设备的 `equipment.status` 设为同一个 `disposition`，提交事务，返回该 `loan_id`。
6. 数据库读写失败时回滚并抛出 `StorageError`；本次归还时间、去向和设备状态修改均不提交。

归还到 `maintenance` 的设备不能通过 S2 的可借条件。本例未提供维护完成后将设备改回 `available` 的处理入口，不能声称维护业务闭环已经实现。

## S4：借用记录查询 `query_loans(borrower_id=None, only_open=False)`

查询使用参数绑定组织 SQL，只执行 SELECT，不修改设备或借用记录：

- 不提供 `borrower_id` 时不按借用人筛选；提供时按该标识相等筛选。这里的参数是查询条件，不构成认证或访问授权。
- `only_open=True` 时增加 `loan.returned_at IS NULL` 条件；否则同时返回符合其他条件的已归还和未归还记录。
- 连接 `equipment` 取得设备名称，返回 `loan_id`、`equipment_id`、设备名称、`borrower_id`、`borrowed_at`、`returned_at`、`return_status`。
- 按 `borrowed_at DESC, loan_id DESC` 排序，借用时间相同时继续按记录编号降序确定顺序。
- 当前返回全部匹配记录，没有分页或导出功能。数据库读取失败抛出 `StorageError`。

## S5：事务与异常的说明口径

S2、S3 中的数据库修改以各自事务为单位提交或回滚，不能描述为两个分别提交的独立写入。前置输入错误、状态拒绝、重复归还、唯一约束冲突和一般存储错误具有不同含义，不能一律写成成功或“自动修复”。本例没有给出错误消息如何在页面展示，也没有给出失败后的自动重试。

可基于上述合成规则解释事务内的修改关系和约束作用；不能把这种机制解释改写为“已证明所有并发情况下均正确”或“实测不会发生数据不一致”。

## S6：未提供的证据与能力

没有实际数据库执行、自动化测试、接口联调、用户观察、部署、性能或并发记录；也没有认证、资源归属、消息通知、预约、逾期、维护完成入口、分页和导出实现。文章可以准确说明这些材料边界，但不能把缺失项写成已实现成果。

本例属于技术实现章教学输入，不包含学校格式规范、用户访谈、研究文献或其他章节的实际内容。两稿对事实的核对仅限 S1—S6，不据此认定真实系统可用。
