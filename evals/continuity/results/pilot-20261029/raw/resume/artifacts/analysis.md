# 项目画像与静态分析（r2）

## 范围、定位与读取基线

本轮按工作目录外层task.md接续已确认的社区订货配送本科软件论文定位与大纲，仍只更新4.3及其图、测试计划、画像和接续登记。project/task.md是旧任务材料，未作为本轮新增指令；没有重开访谈、重写4.1/4.2/4.4或修改project与previous。Markdown仍为正式文本载体。

上次FIRST-SYNTHETIC-SHOP-1.0-R1已全文静态阅读30份来源，形成20模块地图和28项稳定主张。本轮先直接恢复previous/checkpoint.json、analysis.md、chapter.md、flow.mmd、test-plan.md及claims.json；再通过受信material_reader.py清单核对完整路径和text-lf SHA-256。当前31份中新增modules/recalls/service.py，变化modules/orders/service.py、registry.py，删除0份，指纹相同28份；定位与大纲未变。变化最初只标为needs_review，没有直接判旧主张错误。

本轮清单1次，磁盘哈希读取31份、23210字节，不计为模型内容阅读；随后1批--read定向全文读取上述3份、4498字节，无当前项目重复内容读取。为核对新连接，直接复用previous中8份同指纹的原始wrapper返回：store.py及catalog、inventory、refunds、picking、packing、shipping、recovery的service.py；理由是确认冻结、库存释放、退款、packing状态、出库边界、维护筛选和嵌套快照。其他相同指纹来源使用上次充分记录，不机械重新通读。清单/变化报告和本轮原始内容返回分别见inventory-current.json、inventory-diff.json、read-01-changes.json，原始操作记录在工作目录read-log.jsonl。来源内容返回指纹与清单一致。

当前静态修订为registry.py:REVISION=synthetic-shop-1.1，无Git提交/运行发布基线；原synthetic-shop-1.0基线保留在previous及checkpoint历史中。没有实际排除/跳过/发现项；清单不是原子快照。全项目静态画像的接续覆盖为20个旧模块加1个新模块，而本轮实际重读项目仅3份，不能写作重新全文阅读31份。未执行/导入业务、安装、联网、SQL或功能测试。

## 项目画像与材料类型

居民通过资料、商品目录和购物车形成单商户订单。订单先预留库存，记录本地账单、待入账积分和待投事件；本地付款记账后可进入拣货、包装、出库、交付。交付确认触发居民积分入账和商户待结算记录。退货申请/批准只建立售后记录，退款按本地已付余额登记。维护入口从配置获得，按订单创建时间清理仍预留的订单，再尝试发送本地事件。新增商品召回入口先冻结目标商品，再整单取消含该商品且仍reserved或packing的订单，外层快照覆盖整批召回。

主体为居民资料、商户标识及调用业务函数的调用方；材料没有居民身份认证、后台操作员角色、浏览器页面或HTTP服务。`registry.py` 中的路径只是15条函数映射，不能称为已部署API。业务链中只有字符串/ID及状态判断，区域相等判断不是身份认证。

执行模型是单进程内存 `Store`，拥有16个列表表及各自序号，订单行嵌在 `orders.lines`。`transaction` 对整个 `rows` 和 `sequence` 深拷贝，遇 `Exception` 恢复并重抛；不执行SQL，不提供并发锁、持久化或数据库隔离。独立 `schema.sql` 定义15张设计表，含 `customer_order.resident_id REFERENCES resident(id)`、`invoice.order_id UNIQUE` 和 `loyalty.order_id UNIQUE`；这些声明并未约束内存数据，不能将SQL `order_line` 与内存嵌套行混为一个已运行数据库。

证据类别：Python为静态实现；`project.json`为配置声明；SQL为设计草稿；README为背景声明；论文定位/大纲为已确认范围；没有测试源文件、执行报告、截图、真实用户研究、文献或性能材料。未执行的预期仅列测试计划。

## 全部业务模块覆盖

以下每行均有**全文静态内容证据**：20个旧模块复用上次记录及同指纹来源，orders按本轮变化重新核查，recalls为本轮新增全文核查；不是本轮重新通读全部模块。路径均相对project根；完整基线在checkpoint的同路径source中。无业务模块留为未读候选。

| 模块/完整来源路径 | 实际职责与入口 | 关键连接、规则和数据变化 | 主张与限制 |
| --- | --- | --- | --- |
| `modules/residents/service.py` | 居民资料创建及活动状态前置判断；不提供身份认证；registry.py ROUTES[POST /residents] -> register；modules/orders/service.py place -> require_active | orders.place 读取居民活动状态与配送 zone；loyalty.grant 更新居民 points；register 拒绝 strip 后为空的姓名/区域，写 active=True、points=0；require_active 拒绝缺失或 active=False | C-RES-001, C-ORD-001；无认证、角色或调用人凭证；字符串类型等输入未统一校验 |
| `modules/catalog/service.py` | 可售商品查询、下单可售校验及冻结；registry.py ROUTES[GET /catalog] -> list_saleable；orders.place -> require_saleable；recalls.apply -> freeze（召回路由间接调用） | orders.place 从商品读取 merchant_id、price_cents 并冻结到订单行；inventory 以 product_id 关联商品；require_saleable 拒绝缺失/不可售商品；freeze 将 saleable=False | C-CAT-001, C-ORD-002；没有商品/库存初始化的公开入口；种子数据需后续准备 |
| `modules/pricing/service.py` | 逐行检查单价并计算整数分小计；orders.place -> subtotal | 商品当前单价和购物车数量组成 lines -> subtotal -> coupons.discount；type(unit_cents) 必须是 int 且 >0；返回单价乘数量之和；此函数不复核 quantity | C-PRICE-001, C-ORD-002；没有税费引擎；订单创建依赖 cart.put 的数量校验或可信数据 |
| `modules/carts/service.py` | 按居民/商品写入或替换购物车数量，读取居民全部行；registry.py ROUTES[POST /cart-lines] -> put；orders.place -> lines_for | orders.place 消费购物车快照但不删除 cart_lines；数量必须 type is int 且 >0；已有配对行只更新首行；put 不检查居民 active 或商品 saleable | C-CART-001, C-ORD-007；无清空动作、唯一性物理约束或提交幂等键 |
| `modules/coupons/service.py` | 居民归属、活动、到期和门槛判断后的定额抵扣；orders.place -> discount | 接收 pricing.subtotal 的金额；返回抵扣额供 place 扣减；None 返回0；归属不符、停用/缺失拒绝；expires_at < now 才过期；amount < minimum_cents 才不足门槛；返回 min(amount, discount_cents)，不消费或停用券 | C-COUPON-001, C-ORD-007；折扣字段正负等数据约束未统一校验；不存在券领取/配置入口 |
| `modules/inventory/service.py` | 在调用方边界中调整 available/reserved 计数；orders.place -> reserve；orders.cancel -> release；shipping.dispatch -> consume | 按 product_id 查首条库存行；place 扣 available 加 reserved；cancel 反向；shipping 只扣 reserved；stock 缺失拒绝；reserve 检查 available >= quantity；release/consume 检查 reserved >= quantity | C-INV-001, C-ORD-003, C-ORD-004；无锁；数量类型/正数依赖调用链；单商品重复库存行未统一约束 |
| `modules/orders/service.py` | 创建和取消的跨模块编排；registry.py ROUTES[POST /orders] -> place；registry.py ROUTES[POST /orders/cancel] -> cancel；recovery.run/recalls.apply -> cancel | place -> residents/carts/catalog/pricing/coupons -> transaction -> inventory/invoices/loyalty/outbox；cancel -> transaction -> inventory.release -> status cancelled -> captured 时 refunds.issue -> invoices.void -> outbox.enqueue；空购物车拒绝；全部商品可售且 merchant_id 集合恰为1；创建 reserved/unpaid，返回 id；取消允许 reserved或packing，不以是否付款决定可取消性，返回 cancelled | C-ORD-001, C-ORD-002, C-ORD-003, C-ORD-004, C-ORD-005, C-ORD-007；cancel 无操作者/居民参数和归属判断；place 不清购物车/消费券，不做幂等或数量二次校验；取消不调用 loyalty，pending 积分及已有picks/packages留存 |
| `modules/payments/service.py` | 本地付款账目登记；registry.py ROUTES[POST /payments/capture] -> capture | orders reserved/unpaid -> captured，供 picking 和 cancel 读取；refunds 更新 payment.refunded_cents；在 transaction 内检查订单存在、reserved/unpaid、金额等于 total_cents；插入 refunded_cents=0 后改 captured；无正金额单独判断 | C-PAY-001, C-ORD-005；无支付网关；金额类型只由相等比较限制；可接受匹配的零金额 |
| `modules/invoices/service.py` | 创建本地账单及取消时置无效；orders.place -> create；orders.cancel -> void | 和订单、库存、积分、事件共同处于调用方 transaction 内；create 应用层拒绝同订单已存在账单；插入 issued；void 拒绝缺失账单，首条改 void | C-INVOICE-001, C-ORD-003, C-ORD-004；并非税务发票接入；SQL UNIQUE 只属草稿 |
| `modules/picking/service.py` | 已付款预留订单的拣货完成；registry.py ROUTES[POST /picking] -> complete | 读取 orders reserved/captured -> 插 picks done -> order packing，衔接 packing.complete；缺单、非 reserved 或非 captured 拒绝；写操作有 transaction | C-FULFILL-001, C-ORD-004；无拣货人员认证或实际仓库交互 |
| `modules/packing/service.py` | 有拣货记录后生成包装记录；registry.py ROUTES[POST /packing] -> complete | 读取 orders packing、picks done -> 插 packages packed -> shipping.dispatch；缺单/非 packing/无 done 拣货拒绝；已有任意 packages 行拒绝重复；不改订单 packing 状态；自身无 transaction | C-FULFILL-001；无物理包装设备或运输适配器 |
| `modules/shipping/service.py` | 出库消耗预留并生成运输记录与事件；registry.py ROUTES[POST /shipping] -> dispatch | transaction: packing + packed -> inventory.consume 每行 -> orders shipped -> shipments in_transit -> outbox order_shipped；订单/包装前置失败拒绝；shipment.zone 来自订单 zone | C-FULFILL-002；无外部承运商 API；不代表物流已实际发运 |
| `modules/delivery/service.py` | 按运输单保存区域确认交付并触发本地账目；registry.py ROUTES[POST /delivery/confirm] -> confirm | transaction: shipment in_transit + zone匹配 + order shipped -> 二者 delivered -> loyalty.grant -> settlements.accrue；区域不匹配或状态不符拒绝；后续 grant/accrue 异常由 Store 回滚 | C-DELIVERY-001, C-LOYALTY-001, C-SETTLE-001；区域字符串相等不是认证或真实签收证明 |
| `modules/returns/service.py` | 已交付订单的退货申请和审批记录；registry.py ROUTES[POST /returns] -> request；registry.py ROUTES[POST /returns/approve] -> approve | approved 退货记录作为 refunds.issue 的另一许可条件；request 要求 order delivered 且非空原因，写 requested；approve 仅 requested -> approved；不改订单状态、不自动退款或补库存 | C-RETURN-001；无审批人鉴权；可重复申请；无积分/结算冲销联动 |
| `modules/refunds/service.py` | 校验取消/已批准退货与本地已付余额并记退款；registry.py ROUTES[POST /refunds] -> issue；orders.cancel 在 order 改 cancelled 后 -> issue | 读取 returns approved 或 orders cancelled；读取首条 payments -> 更新 refunded_cents -> 全额时 orders.payment_state refunded -> 插 refunds；金额必须 type is int 且 >0；付款存在；不超过 amount_cents-refunded_cents；只有全额退尽才改 refunded；自身无 transaction，由调用方控制 | C-REFUND-001, C-ORD-005, C-ORD-008；公开路由直接调用没有外层 transaction；无外部退款网络；零元 captured 的取消在退款处失败，外层回滚 |
| `modules/notifications/service.py` | 三类事件消息格式化并调用外部传入 transport；outbox.deliver_pending -> send | TEMPLATES 含 order_created/order_cancelled/order_shipped；send -> transport.send；transport None 抛 OSError；否则发送 order_id 和消息文本 | C-NOTIFY-001, C-ORD-006；没有可用 transport 实现；未知模板的 KeyError 不被 outbox 的 OSError 捕获 |
| `modules/outbox/service.py` | 本地事件入队、限批/限次数投递；orders.place/cancel、shipping.dispatch -> enqueue；recovery.run -> deliver_pending | enqueue pending/attempts0；deliver_pending -> notifications.send；按事件 id 升序；只选 pending 且 attempts < max_attempts，取前 limit；成功 attempts+1/sent；OSError attempts+1 保持 pending；返回选中数量而非成功数 | C-OUTBOX-001, C-ORD-006；次数耗尽仍 pending 但不再入选；非 OSError 中断；无去重/幂等保证 |
| `modules/loyalty/service.py` | 按实付订单金额准备积分，交付时入居民账户；orders.place -> prepare；delivery.confirm -> grant | prepare amount_cents//100 -> loyalty pending；grant delivered+首条pending -> residents.points加分、posted；orders.cancel 未调用该模块；grant 非 delivered 或无 pending 拒绝；prepare 没有重复/唯一性检查 | C-LOYALTY-001, C-ORD-003, C-ORD-007；取消保留 pending 记录；售后未冲销积分 |
| `modules/settlements/service.py` | 交付时生成商户待结算记录，按商户记账关闭；delivery.confirm -> accrue；registry.py ROUTES[POST /settlements/close] -> close | accrue delivered -> settlements pending 金额=order.total_cents；close 同商户pending求和->booked；accrue 要求 delivered；close 返回本批总金额；无银行划转 | C-SETTLE-001；accrue 自身不去重；售后/退款没有结算冲销 |
| `modules/recovery/service.py` | 配置绑定的维护入口，超时取消后尝试投递事件；project.json job_handlers.maintenance -> modules.recovery.service:run；app.application -> jobs.runner.task_registry；jobs.runner.invoke 动态装载 -> run | 按 created_at < now-reservation_minutes*60 且 status reserved 选单，id升序 orders.cancel；取消循环全部完成后 outbox.deliver_pending(outbox_batch,max_delivery_attempts,transport)；默认30分钟；等于cutoff不处理；不筛 payment_state；无调度器；单个 cancel 抛错会中断循环和后续通知；已完成的前序取消独立保留 | C-RECOVERY-001, C-ORD-006；无自动定时运行证据；需要显式调用和 transport；maintenance 非全批原子事务 |
| `modules/recalls/service.py` | 新增商品召回编排；registry.py ROUTES[POST /catalog/recall] -> apply | 外层transaction先catalog.freeze；筛选含目标商品的reserved/packing订单，ID升序复用cancel，整单释放各商品库存，返回product_id和cancelled列表；无匹配仍冻结；任一Exception传播至外层恢复整批与冻结 | C-RECALL-001/002；非外部召回平台；不投递通知；无认证、持久化或并发保证；已有拣货/包装/pending积分保留 |

## 基础入口与其他材料覆盖

| 完整路径 | 类型 | 已核实职责及边界 |
| --- | --- | --- |
| `README.md` | document_declaration | 合成材料性质、静态边界和源码优先说明；无运行结果 |
| `app.py` | source_implementation | application 返回 revision、routes、配置任务字典与注入 repository；非 HTTP 服务器 |
| `registry.py` | source_implementation | REVISION=synthetic-shop-1.1；15 条字符串路由到模块函数映射；没有网络/鉴权层 |
| `jobs/runner.py` | source_implementation | task_registry 返回配置映射；invoke 按模块:函数动态分派，传 repo/config/now/transport；不是 scheduler |
| `store.py` | source_implementation | 16 个列表表与序号；get/find 返回行引用；insert 分配序号；transaction 深拷贝 rows+sequence，捕获 Exception 时整体替换并重抛；无 SQL、锁或持久性 |
| `schema.sql` | sql_design_draft | 15张设计表；customer_order.resident_id REFERENCES resident(id)，invoice.order_id 与 loyalty.order_id UNIQUE；与内存结构独立，不被 Store 执行。SQL order_line 与内存 orders.lines 不同 |
| `project.json` | configuration_declaration | currency=CNY-cents；reservation_minutes=30；maintenance绑定；outbox_batch=20；max_delivery_attempts=3；配置存在不等于已运行 |
| `task.md` | task_document | 合成案例旧任务范围和六项产物；本轮以外层task.md为准，无实现证据 |
| `thesis/positioning.md` | confirmed_positioning | 计算机本科社区订货配送；静态源码/配置/SQL；Markdown主稿；不再访谈 |
| `thesis/outline.md` | confirmed_outline | 第四章4.1服务入口、4.2商品库存、4.3创建取消、4.4配送售后维护；本轮只写4.3 |

## 关键业务连接与状态

1. **创建链**：`registry.py:POST /orders → modules/orders/service.py:place → residents.require_active → carts.lines_for → catalog.require_saleable → pricing.subtotal → coupons.discount`。准备时确定单一商户、复制单价与配送区域；随后 `Store.transaction → inventory.reserve（逐行）→ orders.insert → invoices.create → loyalty.prepare → outbox.enqueue`，返回订单ID。交易内异常回滚全内存数据及序号；准备校验失败尚未写业务数据。见C-ORD-001/002/003、C-STORE-001。
2. **取消链**：`POST /orders/cancel → orders.cancel`，或配置后台 `recovery.run → cancel`、召回 `recalls.apply → cancel`。`reserved` 与 `packing` 接受取消；先 `inventory.release`，后写 `cancelled/cancelled_at`，若付款状态为 `captured` 再 `refunds.issue`，随后 `invoices.void`、`outbox.enqueue(order_cancelled)`。顺序使退款能够看到 `cancelled`；退款/账单失败会回滚先前释放与状态，非“部分取消成功”。取消不改pending积分或已有拣货/包装记录，也没有操作者归属校验。见C-ORD-004/005/007/008。
3. **付款与履约链**：`payments.capture` 要求 `reserved/unpaid` 和总额相等，写付款账后变 `captured`；`picking.complete` 将 `reserved/captured → packing`，写 `picks.done`；`packing.complete` 在有done拣货且无已有包装时写 `packages.packed`，订单仍packing；`shipping.dispatch` 消耗reserved、置shipped、写in_transit运输单并排出库事件。picking后及包装后订单仍为packing，可取消；shipping改为shipped后取消被拒绝。见C-PAY-001、C-FULFILL-001/002。
4. **交付与后账链**：`delivery.confirm` 对运输单状态和保存区域做判断，再要求订单shipped；快照内运输单和订单变delivered，`loyalty.grant` 将pending积分计入居民并改posted，`settlements.accrue` 生成商户pending账目。`settlements.close` 按merchant汇总pending并改booked，仅本地记账。见C-DELIVERY-001、C-LOYALTY-001、C-SETTLE-001。
5. **售后链**：`returns.request` 对delivered订单写requested，`returns.approve` 改approved；两者都不自动退款/回库。`refunds.issue` 允许cancelled订单或有approved退货记录的订单，按首条payment的余额累计退款，退尽才改payment_state=refunded；其公开入口没有自身transaction，也没有积分/结算冲销。见C-RETURN-001、C-REFUND-001。
6. **配置后台链**：`app.application → jobs.runner.task_registry(project.json)`；`job_handlers.maintenance → modules.recovery.service:run`，`jobs.runner.invoke`动态取函数并传repo/config/now/transport。`run`严格选择 `created_at < now-30*60` 且reserved的订单，不筛付款状态，按ID逐单取消，之后调用 `outbox.deliver_pending`。这条入口不来自前台菜单，材料没有调度器。取消异常中断本轮后续订单及投递，已经完成的前序订单取消不会被整体撤销。见C-ORD-006、C-RECOVERY-001。
7. **事件投递链**：创建/取消/出库写outbox的pending/attempts=0；维护选择pending且attempts<3，按ID取前20项，交 `notifications.send → 调用方transport.send`。成功变sent、次数加1；OSError只加1并保留pending。达到3次仍pending但不入选，返回值是选中尝试数，不是成功数。没有默认transport时会走OSError分支；非OSError未被该循环捕获。见C-OUTBOX-001、C-NOTIFY-001。

8. **新增召回链**：`POST /catalog/recall → recalls.apply`，外层`Store.transaction → catalog.freeze → find(status in reserved/packing且任一行含目标商品) → ID升序cancel（整单） → 返回product_id/cancelled`。无匹配返回空列表且冻结保留；商品缺失拒绝。任一单失败时内层异常继续传到外层，恢复商品冻结、前序成功取消与全部rows/sequence；与维护无全批快照区分。见C-RECALL-001/002。

订单业务状态主干是 `reserved → packing → shipped → delivered`，`reserved → cancelled` 与 `packing → cancelled`；付款状态独立为 `unpaid → captured → refunded（全额）`。包装状态属于packages而非新增订单状态。取消会释放reserved而出库会消耗reserved；不可把二者都写成“库存回滚”。退款和通知均为本地账目/调用机制，不能称为资金到账和消息送达的实测结果。

## 4.3章节蓝图（Evidence → Design）

| 正文稳定定位 | 解释任务 | 证据/主张 | 图/测试 |
| --- | --- | --- | --- |
| P43-01 | 创建/取消入口、主体和章节边界 | C-CONTEXT-001、C-ORD-001 | FIG-43；TP-01/12 |
| P43-02 | 居民、购物车、可售和单商户前置 | C-RES/CAT/PRICE/CART、C-ORD-001/002 | P1/P2；TP-02—06 |
| P43-03 | 小计、券归属/有效期/门槛/封顶 | C-COUPON-001、C-ORD-002 | P2；TP-07—09 |
| P43-04/05 | 库存—订单—账单—积分—事件顺序及内存回滚 | C-INV、C-ORD-003、C-STORE-001 | P3—PFAIL；TP-01/10/11 |
| P43-06/07 | reserved/packing可取消、出库后拒绝、逐行释放、已付退款、账单作废、失败回滚 | C-ORD-004/005、C-REFUND、C-PAY | C0—CFAIL；TP-12—18 |
| P43-08/09 | 后台时限连接、事件传输边界、零额异常 | C-ORD-006/008、C-RECOVERY/OUTBOX/NOTIFY | M0—M4；TP-18—24 |
| P43-10 | 重复提交、积分和拣货/包装保留、输入/权限/并发边界 | C-ORD-007、C-STORE-001 | TP-25—27/31/35 |
| P43-11 | 新召回入口、商品冻结、整单选择、嵌套快照和整批失败边界 | C-RECALL-001/002、C-CAT-001、C-STORE-001 | R0—RFAIL；TP-32—35 |

4.1负责完整服务组织与入口；4.2负责商品库存准备；4.4负责详细履约/售后/维护。本节只解释这些模块如何影响创建、取消和可取消状态，避免重复展开后续履约。

## 变化提示到语义复核

registry和orders变化使13项已有登记主张进入需复核范围；它们并不全部错误。逐条结果记录于claims.json:review和checkpoint.json:change_review。C-ORD-004的“仅reserved”已修订为reserved/packing；C-ORD-007保留原有边界并补明已有拣货/包装记录不清理。其余11项受提示主张的原处理规则仍成立：订单创建整段未变、退款与零额边界未变、函数映射仍不构成HTTP/鉴权层。未变化主张沿用同指纹及上次记录，不宣称本轮重新证明全部实现。

新增C-RECALL-001登记入口、冻结、匹配、顺序与整单取消，C-RECALL-002登记外层快照及失败传播。必要连接复核确认picking将订单改packing、packing只写packages、shipping才消耗预留；因此扩大取消无需补造库存回补逻辑，取消也不会清除picks/packages。recovery仍只选reserved，不能把cancel条件扩展传播成“维护会取消packing”。召回不直接调用投递，不能把取消事件入队写为通知成功。

## 本轮Technical Review

按变化定位核对了P43-01/06/08/10及新增P43-11，P43-07/09的退款顺序与零额失败继续有效。FIG-43的C2已扩大条件，C9补明记录保留；M1仍仅reserved，新增R0—RFAIL区分召回外层与逐单取消快照。新增召回返回顺序、无匹配、缺商品、整单其他商品、已出库排除及后单失败整批恢复均有静态来源，未将嵌套快照扩写为数据库事务、并发隔离或持久化。

测试计划修订TP-14、补明TP-20，新增TP-31—35，现为35项未执行计划。正常路径、状态边界和失败后rows/sequence检查均为待验证预期；没有通过数或通过率。新增异常夹具与正常可达业务状态分开。原有未受影响测试继续保留。

## 本轮Academic Review与交付状态

本轮仅采用工作目录rules/references/academic-style.md内置规则，未读取或声称调用全局技能。先登记事实问题及改法，再修改受影响段落：将“拣货后不能取消”改为出库边界；补出召回主体、匹配范围、整单行为、失败传播与维护差异；统一预留、包装、出库、本地账目、待投事件术语。保留已有数字及未执行限定，无关段落不重写。

Evidence定向复核、Design局部蓝图、Draft、Technical Review、Academic Review及本轮六份成果更新完成。FIG-43交付可编辑Mermaid源，内容已核对，未调用渲染器、未导出查看、未入Word或验收页面。业务、SQL、测试、部署、性能及外部服务均未运行；本轮是静态材料实现说明。

## 接续方法

从本轮checkpoint恢复已确认定位、21模块地图、15条函数映射、30项稳定主张及当前31份指纹；previous保留r1历史。下一轮先用同一wrapper清单比较，来源变更仍只提示复核。若无变化，不再读项目内容；若订单/召回变化，先读变化源，再按claims中的P43/C/R/TP定位和已有连接选择必要材料。图源渲染查看和运行验证保持独立待办，不用结构核对替代。

读取口径补充：为选出必要连接，Python装载了previous/read-01至read-05五份旧JSON缓存（包含30份旧来源文本），仅向模型显示上述8份完整源文本，另显示旧orders/registry的差异片段。它们不同于本轮wrapper读取的3份当前源码，也不同于checkpoint/正式产物摘要复用；具体文件与逐项理由见read-scope.json。未读取previous/build_artifacts.py内容，仅目录列举过其名称和大小。
