"""Author artifacts from trusted reader JSON only; never open/import project files."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
logs = [json.loads(x) for x in (ROOT / "read-log.jsonl").read_text(encoding="utf-8-sig").splitlines() if x.strip()]
inventory = next(x["report"] for x in logs if x["action"] == "inventory")
reads = {}
for raw in sorted(OUT.glob("read-*.json")):
    for f in json.loads(raw.read_text(encoding="utf-8-sig"))["files"]:
        assert f["path"] not in reads, f["path"]
        reads[f["path"]] = dict(f, reader_artifact=raw.name)
assert set(reads) == {x["path"] for x in inventory["files"]}

def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def source(path, locator="whole file"):
    f = reads[path]
    return {"path": path, "sha256": f["sha256_text_lf"], "hash_mode": "text-lf", "locator": locator}

def module(name, duties, functions, entries, calls, data, rules, unknowns, claim_ids):
    path = "modules/" + name + "/service.py"
    return {"module_id": "M-" + name.upper(), "name": name, "source": source(path),
            "responsibility": duties, "functions": functions, "entries": entries,
            "key_connections": calls, "data": data, "confirmed_rules": rules,
            "coverage": "full_static_content_read", "evidence_type": "source_implementation_not_executed",
            "open_items": unknowns, "claim_ids": claim_ids}

modules = [
module("residents", "居民资料创建及活动状态前置判断；不提供身份认证", ["register", "require_active"],
       ["registry.py ROUTES[POST /residents] -> register", "modules/orders/service.py place -> require_active"],
       ["orders.place 读取居民活动状态与配送 zone", "loyalty.grant 更新居民 points"],
       ["residents: name, zone, active, points"],
       ["register 拒绝 strip 后为空的姓名/区域，写 active=True、points=0", "require_active 拒绝缺失或 active=False"],
       ["无认证、角色或调用人凭证；字符串类型等输入未统一校验"], ["C-RES-001", "C-ORD-001"]),
module("catalog", "可售商品查询、下单可售校验及冻结", ["list_saleable", "require_saleable", "freeze"],
       ["registry.py ROUTES[GET /catalog] -> list_saleable", "orders.place -> require_saleable", "freeze 为未注册路由的函数入口"],
       ["orders.place 从商品读取 merchant_id、price_cents 并冻结到订单行", "inventory 以 product_id 关联商品"],
       ["catalog: saleable, merchant_id, price_cents"],
       ["require_saleable 拒绝缺失/不可售商品", "freeze 将 saleable=False"],
       ["没有商品/库存初始化的公开入口；种子数据需后续准备"], ["C-CAT-001", "C-ORD-002"]),
module("pricing", "逐行检查单价并计算整数分小计", ["subtotal"], ["orders.place -> subtotal"],
       ["商品当前单价和购物车数量组成 lines -> subtotal -> coupons.discount"],
       ["order.lines: product_id, quantity, unit_cents"],
       ["type(unit_cents) 必须是 int 且 >0；返回单价乘数量之和", "此函数不复核 quantity"],
       ["没有税费引擎；订单创建依赖 cart.put 的数量校验或可信数据"], ["C-PRICE-001", "C-ORD-002"]),
module("carts", "按居民/商品写入或替换购物车数量，读取居民全部行", ["put", "lines_for"],
       ["registry.py ROUTES[POST /cart-lines] -> put", "orders.place -> lines_for"],
       ["orders.place 消费购物车快照但不删除 cart_lines"],
       ["cart_lines: resident_id, product_id, quantity"],
       ["数量必须 type is int 且 >0；已有配对行只更新首行", "put 不检查居民 active 或商品 saleable"],
       ["无清空动作、唯一性物理约束或提交幂等键"], ["C-CART-001", "C-ORD-007"]),
module("coupons", "居民归属、活动、到期和门槛判断后的定额抵扣", ["discount"], ["orders.place -> discount"],
       ["接收 pricing.subtotal 的金额；返回抵扣额供 place 扣减"],
       ["coupons: resident_id, active, expires_at, minimum_cents, discount_cents"],
       ["None 返回0；归属不符、停用/缺失拒绝", "expires_at < now 才过期；amount < minimum_cents 才不足门槛", "返回 min(amount, discount_cents)，不消费或停用券"],
       ["折扣字段正负等数据约束未统一校验；不存在券领取/配置入口"], ["C-COUPON-001", "C-ORD-007"]),
module("inventory", "在调用方边界中调整 available/reserved 计数", ["stock", "reserve", "release", "consume"],
       ["orders.place -> reserve", "orders.cancel -> release", "shipping.dispatch -> consume"],
       ["按 product_id 查首条库存行", "place 扣 available 加 reserved；cancel 反向；shipping 只扣 reserved"],
       ["inventory: product_id, available, reserved"],
       ["stock 缺失拒绝；reserve 检查 available >= quantity", "release/consume 检查 reserved >= quantity"],
       ["无锁；数量类型/正数依赖调用链；单商品重复库存行未统一约束"], ["C-INV-001", "C-ORD-003", "C-ORD-004"]),
module("orders", "创建和取消的跨模块编排", ["place", "cancel"],
       ["registry.py ROUTES[POST /orders] -> place", "registry.py ROUTES[POST /orders/cancel] -> cancel", "recovery.run -> cancel"],
       ["place -> residents/carts/catalog/pricing/coupons -> transaction -> inventory/invoices/loyalty/outbox",
        "cancel -> transaction -> inventory.release -> status cancelled -> captured 时 refunds.issue -> invoices.void -> outbox.enqueue"],
       ["orders: resident_id, merchant_id, zone, status, payment_state, total_cents, created_at, lines, cancelled_at"],
       ["空购物车拒绝；全部商品可售且 merchant_id 集合恰为1", "创建 reserved/unpaid，返回 id", "取消仅允许 reserved，不以是否付款决定可取消性，返回 cancelled"],
       ["cancel 无操作者/居民参数和归属判断", "place 不清购物车/消费券，不做幂等或数量二次校验", "取消不调用 loyalty，pending 积分留存"],
       ["C-ORD-001", "C-ORD-002", "C-ORD-003", "C-ORD-004", "C-ORD-005", "C-ORD-007"]),
module("payments", "本地付款账目登记", ["capture"], ["registry.py ROUTES[POST /payments/capture] -> capture"],
       ["orders reserved/unpaid -> captured，供 picking 和 cancel 读取", "refunds 更新 payment.refunded_cents"],
       ["payments: order_id, amount_cents, refunded_cents", "orders.payment_state"],
       ["在 transaction 内检查订单存在、reserved/unpaid、金额等于 total_cents", "插入 refunded_cents=0 后改 captured；无正金额单独判断"],
       ["无支付网关；金额类型只由相等比较限制；可接受匹配的零金额"], ["C-PAY-001", "C-ORD-005"]),
module("invoices", "创建本地账单及取消时置无效", ["create", "void"],
       ["orders.place -> create", "orders.cancel -> void"],
       ["和订单、库存、积分、事件共同处于调用方 transaction 内"],
       ["invoices: order_id, amount_cents, status"],
       ["create 应用层拒绝同订单已存在账单；插入 issued", "void 拒绝缺失账单，首条改 void"],
       ["并非税务发票接入；SQL UNIQUE 只属草稿"], ["C-INVOICE-001", "C-ORD-003", "C-ORD-004"]),
module("picking", "已付款预留订单的拣货完成", ["complete"], ["registry.py ROUTES[POST /picking] -> complete"],
       ["读取 orders reserved/captured -> 插 picks done -> order packing，衔接 packing.complete"],
       ["picks: order_id, status", "orders.status"],
       ["缺单、非 reserved 或非 captured 拒绝；写操作有 transaction"],
       ["无拣货人员认证或实际仓库交互"], ["C-FULFILL-001", "C-ORD-004"]),
module("packing", "有拣货记录后生成包装记录", ["complete"], ["registry.py ROUTES[POST /packing] -> complete"],
       ["读取 orders packing、picks done -> 插 packages packed -> shipping.dispatch"],
       ["packages: order_id, status"],
       ["缺单/非 packing/无 done 拣货拒绝；已有任意 packages 行拒绝重复", "不改订单 packing 状态；自身无 transaction"],
       ["无物理包装设备或运输适配器"], ["C-FULFILL-001"]),
module("shipping", "出库消耗预留并生成运输记录与事件", ["dispatch"], ["registry.py ROUTES[POST /shipping] -> dispatch"],
       ["transaction: packing + packed -> inventory.consume 每行 -> orders shipped -> shipments in_transit -> outbox order_shipped"],
       ["orders.status", "inventory.reserved", "shipments: order_id, zone, status", "outbox"],
       ["订单/包装前置失败拒绝；shipment.zone 来自订单 zone"],
       ["无外部承运商 API；不代表物流已实际发运"], ["C-FULFILL-002"]),
module("delivery", "按运输单保存区域确认交付并触发本地账目", ["confirm"], ["registry.py ROUTES[POST /delivery/confirm] -> confirm"],
       ["transaction: shipment in_transit + zone匹配 + order shipped -> 二者 delivered -> loyalty.grant -> settlements.accrue"],
       ["shipments.status", "orders.status", "residents.points", "loyalty.status", "settlements"],
       ["区域不匹配或状态不符拒绝；后续 grant/accrue 异常由 Store 回滚"],
       ["区域字符串相等不是认证或真实签收证明"], ["C-DELIVERY-001", "C-LOYALTY-001", "C-SETTLE-001"]),
module("returns", "已交付订单的退货申请和审批记录", ["request", "approve"],
       ["registry.py ROUTES[POST /returns] -> request", "registry.py ROUTES[POST /returns/approve] -> approve"],
       ["approved 退货记录作为 refunds.issue 的另一许可条件"],
       ["returns: order_id, reason, status"],
       ["request 要求 order delivered 且非空原因，写 requested", "approve 仅 requested -> approved；不改订单状态、不自动退款或补库存"],
       ["无审批人鉴权；可重复申请；无积分/结算冲销联动"], ["C-RETURN-001"]),
module("refunds", "校验取消/已批准退货与本地已付余额并记退款", ["issue"],
       ["registry.py ROUTES[POST /refunds] -> issue", "orders.cancel 在 order 改 cancelled 后 -> issue"],
       ["读取 returns approved 或 orders cancelled；读取首条 payments -> 更新 refunded_cents -> 全额时 orders.payment_state refunded -> 插 refunds"],
       ["payments.refunded_cents", "orders.payment_state", "refunds: order_id, amount_cents"],
       ["金额必须 type is int 且 >0；付款存在；不超过 amount_cents-refunded_cents", "只有全额退尽才改 refunded；自身无 transaction，由调用方控制"],
       ["公开路由直接调用没有外层 transaction；无外部退款网络", "零元 captured 的取消在退款处失败，外层回滚"], ["C-REFUND-001", "C-ORD-005", "C-ORD-008"]),
module("notifications", "三类事件消息格式化并调用外部传入 transport", ["send"], ["outbox.deliver_pending -> send"],
       ["TEMPLATES 含 order_created/order_cancelled/order_shipped；send -> transport.send"],
       ["event.kind, order_id；不直接写库"],
       ["transport None 抛 OSError；否则发送 order_id 和消息文本"],
       ["没有可用 transport 实现；未知模板的 KeyError 不被 outbox 的 OSError 捕获"], ["C-NOTIFY-001", "C-ORD-006"]),
module("outbox", "本地事件入队、限批/限次数投递", ["enqueue", "deliver_pending"],
       ["orders.place/cancel、shipping.dispatch -> enqueue", "recovery.run -> deliver_pending"],
       ["enqueue pending/attempts0；deliver_pending -> notifications.send；按事件 id 升序"],
       ["outbox: kind, order_id, status, attempts"],
       ["只选 pending 且 attempts < max_attempts，取前 limit", "成功 attempts+1/sent；OSError attempts+1 保持 pending；返回选中数量而非成功数"],
       ["次数耗尽仍 pending 但不再入选；非 OSError 中断；无去重/幂等保证"], ["C-OUTBOX-001", "C-ORD-006"]),
module("loyalty", "按实付订单金额准备积分，交付时入居民账户", ["prepare", "grant"],
       ["orders.place -> prepare", "delivery.confirm -> grant"],
       ["prepare amount_cents//100 -> loyalty pending；grant delivered+首条pending -> residents.points加分、posted", "orders.cancel 未调用该模块"],
       ["loyalty: order_id, resident_id, points, status", "residents.points"],
       ["grant 非 delivered 或无 pending 拒绝；prepare 没有重复/唯一性检查"],
       ["取消保留 pending 记录；售后未冲销积分"], ["C-LOYALTY-001", "C-ORD-003", "C-ORD-007"]),
module("settlements", "交付时生成商户待结算记录，按商户记账关闭", ["accrue", "close"],
       ["delivery.confirm -> accrue", "registry.py ROUTES[POST /settlements/close] -> close"],
       ["accrue delivered -> settlements pending 金额=order.total_cents；close 同商户pending求和->booked"],
       ["settlements: order_id, merchant_id, amount_cents, status"],
       ["accrue 要求 delivered；close 返回本批总金额；无银行划转"],
       ["accrue 自身不去重；售后/退款没有结算冲销"], ["C-SETTLE-001"]),
module("recovery", "配置绑定的维护入口，超时取消后尝试投递事件", ["run"],
       ["project.json job_handlers.maintenance -> modules.recovery.service:run", "app.application -> jobs.runner.task_registry；jobs.runner.invoke 动态装载 -> run"],
       ["按 created_at < now-reservation_minutes*60 且 status reserved 选单，id升序 orders.cancel", "取消循环全部完成后 outbox.deliver_pending(outbox_batch,max_delivery_attempts,transport)"],
       ["orders/inventory/payments/refunds/invoices/outbox，间接更新"],
       ["默认30分钟；等于cutoff不处理；不筛 payment_state", "无调度器；单个 cancel 抛错会中断循环和后续通知；已完成的前序取消独立保留"],
       ["无自动定时运行证据；需要显式调用和 transport；maintenance 非全批原子事务"], ["C-RECOVERY-001", "C-ORD-006"]),
]

infrastructure = [
 {"path":"README.md", "type":"document_declaration", "role":"合成材料性质、静态边界和源码优先说明；无运行结果"},
 {"path":"app.py", "type":"source_implementation", "role":"application 返回 revision、routes、配置任务字典与注入 repository；非 HTTP 服务器"},
 {"path":"registry.py", "type":"source_implementation", "role":"REVISION=synthetic-shop-1.0；14 条字符串路由到模块函数映射；没有网络/鉴权层"},
 {"path":"jobs/runner.py", "type":"source_implementation", "role":"task_registry 返回配置映射；invoke 按模块:函数动态分派，传 repo/config/now/transport；不是 scheduler"},
 {"path":"store.py", "type":"source_implementation", "role":"16 个列表表与序号；get/find 返回行引用；insert 分配序号；transaction 深拷贝 rows+sequence，捕获 Exception 时整体替换并重抛；无 SQL、锁或持久性"},
 {"path":"schema.sql", "type":"sql_design_draft", "role":"15张设计表；customer_order.resident_id REFERENCES resident(id)，invoice.order_id 与 loyalty.order_id UNIQUE；与内存结构独立，不被 Store 执行。SQL order_line 与内存 orders.lines 不同"},
 {"path":"project.json", "type":"configuration_declaration", "role":"currency=CNY-cents；reservation_minutes=30；maintenance绑定；outbox_batch=20；max_delivery_attempts=3；配置存在不等于已运行"},
 {"path":"task.md", "type":"task_document", "role":"合成案例本轮范围和六项产物；无实现证据"},
 {"path":"thesis/positioning.md", "type":"confirmed_positioning", "role":"计算机本科社区订货配送；静态源码/配置/SQL；Markdown主稿；不再访谈"},
 {"path":"thesis/outline.md", "type":"confirmed_outline", "role":"第四章4.1服务入口、4.2商品库存、4.3创建取消、4.4配送售后维护；本轮只写4.3"},
]

connections = []
for m in modules:
    for n, edge in enumerate(m["key_connections"], 1):
        connections.append({"connection_id": m["module_id"] + "-K" + str(n), "description": edge, "source_path": m["source"]["path"], "claim_ids": m["claim_ids"]})

claim_specs = [
 ("C-CONTEXT-001", "该材料是合成社区订货配送服务；app和registry只组织函数入口，非实际HTTP/鉴权服务。", [("README.md","全文"),("app.py","application"),("registry.py","REVISION, ROUTES"),("thesis/positioning.md","已确认定位")], ["P43-01"], [], []),
 ("C-STORE-001", "Store.transaction是rows和sequence深拷贝快照；Exception时恢复并重抛，不提供SQL事务、持久化或并发锁。", [("store.py","Store.transaction, TABLES"),("schema.sql","首行说明及独立表定义")], ["P43-05","P43-07","P43-10"], ["PFAIL","CFAIL","P3","C1"], ["TP-10","TP-16","TP-17","TP-24"]),
 ("C-RES-001", "居民注册拒绝空姓名/区域并初始化活动状态与积分；require_active供创建订单校验。", [("modules/residents/service.py","register, require_active")], ["P43-02"], ["P1"], ["TP-02"]),
 ("C-CAT-001", "目录只返回可售商品；下单拒绝缺失/不可售商品，freeze关闭可售标志。", [("modules/catalog/service.py","list_saleable, require_saleable, freeze")], ["P43-02"], ["P2"], ["TP-04"]),
 ("C-PRICE-001", "subtotal校验正整数分单价后计算单价乘数量之和；数量校验位于cart.put，不在place重复执行。", [("modules/pricing/service.py","subtotal"),("modules/carts/service.py","put"),("modules/orders/service.py","place")], ["P43-02","P43-03","P43-10"], ["P2"], ["TP-03","TP-06","TP-27"]),
 ("C-CART-001", "购物车按居民/商品更新首条数量；创建订单读取但不清空购物车。", [("modules/carts/service.py","put, lines_for"),("modules/orders/service.py","place")], ["P43-02","P43-10"], ["P1"], ["TP-01","TP-27"]),
 ("C-COUPON-001", "优惠券可选，要求归属且活动；过期判断严格小于now，金额门槛可相等，抵扣=min(小计,discount_cents)，不消费券。", [("modules/coupons/service.py","discount"),("modules/orders/service.py","place金额计算")], ["P43-03","P43-10"], ["P2"], ["TP-07","TP-08","TP-09","TP-27"]),
 ("C-INV-001", "reserve可用转预留，release预留转可用，consume只减少预留；库存缺失或不足会抛ValueError。", [("modules/inventory/service.py","stock, reserve, release, consume")], ["P43-04","P43-06"], ["P4","C3"], ["TP-01","TP-10","TP-12","TP-16"]),
 ("C-ORD-001", "POST /orders映射place；创建先查活动居民和非空购物车，再查每个商品可售，所有商品必须恰属一个商户。", [("registry.py","ROUTES[POST /orders]"),("modules/orders/service.py","place前半段"),("modules/residents/service.py","require_active"),("modules/catalog/service.py","require_saleable")], ["P43-01","P43-02"], ["P0","P1","P2"], ["TP-01","TP-02","TP-03","TP-04","TP-05"]),
 ("C-ORD-002", "订单行复制当前商品ID/价格与购物车数量，形成小计再减券额；订单复制居民区域和单一商户。", [("modules/orders/service.py","place构造lines、amount及orders插入"),("modules/pricing/service.py","subtotal"),("modules/coupons/service.py","discount")], ["P43-02","P43-03","P43-04"], ["P2","P5"], ["TP-01","TP-06","TP-07","TP-08"]),
 ("C-ORD-003", "创建的快照边界依次预留库存、写reserved/unpaid订单、issued账单、pending积分、order_created待投事件，返回订单ID。", [("modules/orders/service.py","place with repo.transaction"),("modules/invoices/service.py","create"),("modules/loyalty/service.py","prepare"),("modules/outbox/service.py","enqueue"),("store.py","transaction")], ["P43-04","P43-05"], ["P3","P4","P5","P6","P7","P8","P9","PFAIL"], ["TP-01","TP-10","TP-11"]),
 ("C-ORD-004", "取消仅接受reserved；在快照内逐行释放库存、置cancelled并记录时间、条件退款、作废账单、入队取消事件。", [("modules/orders/service.py","cancel"),("modules/inventory/service.py","release"),("modules/invoices/service.py","void"),("modules/outbox/service.py","enqueue"),("modules/picking/service.py","complete")], ["P43-06","P43-07"], ["C0","C1","C2","C3","C4","C5","C7","C8","C9","CFAIL"], ["TP-12","TP-13","TP-14","TP-16","TP-17"]),
 ("C-ORD-005", "cancel在状态改cancelled后，captured分支按total_cents调用refunds.issue，校验付款及正整数金额和余额；足额退款使payment_state=refunded。", [("modules/orders/service.py","cancel captured分支"),("modules/refunds/service.py","issue"),("modules/payments/service.py","capture")], ["P43-07","P43-09"], ["C5","C6"], ["TP-13","TP-15","TP-18"]),
 ("C-ORD-006", "维护入口由配置绑定，严格早于30分钟前且仍reserved的订单按ID取消，包括captured订单，然后限批投递事件；没有内置调度器或传输适配器。", [("project.json","job_handlers, reservation_minutes, outbox_batch, max_delivery_attempts"),("jobs/runner.py","task_registry, invoke"),("modules/recovery/service.py","run"),("modules/outbox/service.py","deliver_pending"),("modules/notifications/service.py","send")], ["P43-08","P43-09"], ["M0","M1","M2","M3","M4"], ["TP-19","TP-20","TP-21","TP-22","TP-23","TP-24"]),
 ("C-ORD-007", "创建不清购物车/消费券/去重；取消不撤销pending积分，且取消入口没有调用人归属校验。", [("modules/orders/service.py","place, cancel完整读写范围"),("modules/coupons/service.py","discount"),("modules/loyalty/service.py","prepare, grant"),("registry.py","无鉴权层的映射")], ["P43-10"], [], ["TP-25","TP-26","TP-27"]),
 ("C-ORD-008", "券可使订单总额为0；capture未拒绝匹配的0金额，但取消captured零元订单时refunds正数校验失败并回滚取消。", [("modules/coupons/service.py","discount返回min"),("modules/payments/service.py","capture金额比较"),("modules/orders/service.py","cancel退款分支"),("modules/refunds/service.py","issue正数判断"),("store.py","transaction")], ["P43-09"], ["C6","CFAIL"], ["TP-09","TP-18"]),
 ("C-PAY-001", "本地付款仅允许reserved/unpaid且金额匹配，插payments并置captured；无支付网关。", [("modules/payments/service.py","capture")], ["P43-07","P43-09"], ["C5"], ["TP-13","TP-18","TP-28"]),
 ("C-INVOICE-001", "本地账单create应用层去重并写issued；void要求存在并置void；非税务接口。", [("modules/invoices/service.py","create, void")], ["P43-04","P43-07"], ["P6","C7"], ["TP-01","TP-12","TP-17"]),
 ("C-FULFILL-001", "拣货将reserved/captured改packing并写done；包装要求packing及done拣货且无包装，写packed但不改订单状态。", [("modules/picking/service.py","complete"),("modules/packing/service.py","complete")], ["P43-06"], ["C2"], ["TP-14"]),
 ("C-FULFILL-002", "出库需packing与packed，在快照内消耗预留、置shipped、建in_transit运输单并入队order_shipped。", [("modules/shipping/service.py","dispatch"),("modules/inventory/service.py","consume")], [], [], ["TP-29"]),
 ("C-DELIVERY-001", "交付确认核运输单in_transit与区域、订单shipped，快照内置delivered并调用积分入账和结算生成。", [("modules/delivery/service.py","confirm"),("modules/loyalty/service.py","grant"),("modules/settlements/service.py","accrue")], [], [], ["TP-29"]),
 ("C-RETURN-001", "退货申请仅delivered且原因非空，requested可审批为approved，不自动退款或回库。", [("modules/returns/service.py","request, approve"),("modules/refunds/service.py","issue许可条件")], [], [], ["TP-30"]),
 ("C-REFUND-001", "退款可由cancelled订单或approved退货触发，按首条付款余额记账；issue自身无快照边界，公开映射直接调用。", [("modules/refunds/service.py","issue"),("registry.py","ROUTES[POST /refunds]"),("modules/orders/service.py","cancel调用顺序")], ["P43-07"], ["C6"], ["TP-13","TP-15","TP-30"]),
 ("C-LOYALTY-001", "创建pending积分=total_cents//100；delivered时grant将首条pending积分计入居民并改posted；取消未清理。", [("modules/loyalty/service.py","prepare, grant"),("modules/orders/service.py","place, cancel"),("modules/delivery/service.py","confirm")], ["P43-04","P43-10"], ["P7"], ["TP-01","TP-26","TP-29"]),
 ("C-SETTLE-001", "交付时按订单总额生成商户pending结算；close按商户求和后置booked，非银行划转。", [("modules/settlements/service.py","accrue, close"),("modules/delivery/service.py","confirm")], [], [], ["TP-29","TP-30"]),
 ("C-OUTBOX-001", "投递选pending且attempts<上限，按ID限批；成功加次并sent，OSError只加次；返回尝试数，耗尽仍pending。", [("modules/outbox/service.py","enqueue, deliver_pending"),("project.json","outbox_batch=20, max_delivery_attempts=3")], ["P43-09"], ["M4"], ["TP-21","TP-22","TP-23"]),
 ("C-NOTIFY-001", "通知仅格式化创建/取消/出库消息并调用传入transport，None抛OSError，无内置传输。", [("modules/notifications/service.py","TEMPLATES, send")], ["P43-09"], ["M4"], ["TP-21","TP-23"]),
 ("C-RECOVERY-001", "maintenance按配置动态分派到recovery.run；逐单快照取消后投递，单单异常中断后续，全批不原子。", [("project.json","job_handlers"),("jobs/runner.py","invoke"),("modules/recovery/service.py","run")], ["P43-08","P43-09"], ["M0","M1","M2","M3","M4"], ["TP-19","TP-20","TP-24"]),
]
claims = []
for cid, statement, origins, pars, nodes, cases in claim_specs:
    targets = [{"kind":"analysis","path":"analysis.md","locator":"模块覆盖表或关键连接；"+cid}]
    targets += [{"kind":"chapter","path":"chapter.md","locator":p} for p in pars]
    targets += [{"kind":"figure","path":"flow.mmd","locator":"FIG-43 node "+n} for n in nodes]
    targets += [{"kind":"test","path":"test-plan.md","locator":t} for t in cases]
    claims.append({"claim_id":cid,"statement":statement,"evidence_type":"static_source/config/sql_as_marked",
                   "status":"confirmed_static_not_runtime", "sources":[source(p,l) for p,l in origins], "targets":targets})
manifest = {"schema_version":1,"source_root":"project/ (explicit absolute root in checkpoint.json)",
            "target_root":"artifacts/", "revision":"synthetic-shop-1.0", "hash_algorithm":"SHA-256", "hash_mode":"text-lf",
            "claims":claims,"rename_candidates":[],"rename_roots":[],
            "limits":["路径/指纹变化仅提示复核，不直接证伪主张；本轮未执行项目或业务测试。", "来源路径相对project，目标路径相对artifacts，检查工具调用时必须显式处理这两个根。"]}
write_json("claims.json", manifest)
write_json("inventory-baseline.json", inventory)

source_records = []
for item in inventory["files"]:
    f = reads[item["path"]]
    assert item["sha256"] == f["sha256_text_lf"]
    s = source(f["path"], "全文；行范围1-"+str(len(f["text"].splitlines())))
    s.update({"bytes":f["bytes"],"mtime_ns":item["mtime_ns"],"model_read_status":"full_text_read_once", "reader_artifact":f["reader_artifact"],
              "source_claim_ids":[c["claim_id"] for c in claims if any(x["path"]==f["path"] for x in c["sources"])]})
    source_records.append(s)

open_items = [
 {"id":"U-RUNTIME","scope":"本轮所有功能","issue":"无业务执行、实际测试、部署、性能或外部服务证据；测试计划可执行性需后续确认。","next":"在另获授权且环境可用时准备数据/桩与运行记录，不安装或运行本轮材料。"},
 {"id":"U-DIAGRAM","scope":"flow.mmd","issue":"交付可编辑Mermaid源；未调用渲染器，未导出查看或入Word页面。","next":"后续选本地已有渲染器，核中文、交叉线、分支与目标页面。"},
 {"id":"U-IDENTITY","scope":"取消及公开入口","issue":"未提供认证/调用人归属参数；不能声称居民只能取消本人订单。","next":"保留限制；若新材料新增鉴权再定向核查registry/orders及新入口。"},
 {"id":"U-DATA","scope":"创建/取消输入","issue":"place不二次校验购物车数量；商品、券、库存初始化数据无统一校验入口。","next":"区分经cart.put的数据与直接污染数据；TP-27观察边界，不虚构增强校验。"},
 {"id":"U-ZERO","scope":"零额付款取消","issue":"静态链可形成captured零元订单，cancel退款正数校验失败而回滚。","next":"TP-18后续复现；实现未变前不将该路径写为已支持。"},
 {"id":"U-PENDING","scope":"取消积分/售后账目","issue":"取消不撤销pending积分；退货/退款无积分/结算冲销。","next":"保留已确认边界，后续变更需同时核loyalty/orders/delivery/returns/refunds/settlements。"},
 {"id":"U-ATOMIC","scope":"内存与后台","issue":"仅单进程Exception快照恢复；公开refunds、packing、returns、settlement.close无自身快照；maintenance无全批事务。","next":"不写持久性、并发隔离、全批原子性或所有入口一致性保证。"},
 {"id":"U-SQL","scope":"schema.sql","issue":"SQL为独立设计草稿，未执行，表名/行结构不同于Store。","next":"不能将SQL外键/唯一性迁移到内存实现结论；有运行库材料时另核。"},
]

checkpoint = {
 "schema_version":2,"checkpoint_id":"FIRST-SYNTHETIC-SHOP-1.0-R1","artifact_revision":"r1","date":"2026-10-29",
 "task":"完整静态项目画像后，编写4.3订单创建与取消、流程图源、测试计划与可恢复证据登记。",
 "workspace_root":str(ROOT),"source_root":inventory["root"],"artifact_root":str(OUT),
 "authorization":{"synthetic_only":True,"no_network":True,"no_project_execution_or_import":True,"no_dependency_installation":True,"no_real_user_questions":True,"project_read_only":True,"project_access_only_via_trusted_material_reader":True},
 "confirmed_positioning":{"topic":"社区订货配送","level":"计算机本科软件设计与实现","focus":["实际业务规则","跨模块调用","状态及本地账目变化","实现边界"],"authoritative_format":"Markdown","confirmed":True,"interview_needed":False,"sources":[source("thesis/positioning.md"),source("thesis/outline.md")]},
 "outline":{"4.1":"服务组织与入口","4.2":"商品及库存准备","4.3":"订单创建与取消","4.4":"配送、售后与维护处理","current_scope":"只写4.3；完整分析覆盖4.4关联模块，正文仅取边界和维护取消连接。"},
 "source_revision":{"value":"synthetic-shop-1.0","source":source("registry.py","REVISION"),"git_state":"未取得Git提交基线；没有用文件mtime推定提交或实际发布。"},
 "evidence_scope":{"full_business_coverage":True,"business_modules":20,"all_inventory_paths_model_read":True,"runtime_executed":False,"business_tests_executed":False,"sql_executed":False,"deployed":False,"third_party_sources":False,"claims_status":"静态已核实，非运行成功结论"},
 "inventory_baseline":{"path":"inventory-baseline.json","report_status":inventory["status"],"files":inventory["files"],"excluded":inventory["excluded"],"skipped":inventory["skipped"],"findings":inventory["findings"],"default_excluded_names":inventory["coverage"]["default_excluded_names"],"scope_note":"本次无实际排除/跳过；非原子快照，不保证并发替换隔离。"},
 "reading_measurement":{"inventory_calls":1,"inventory_hash_disk_reads":30,"inventory_hash_bytes":22448,"inventory_model_content_reads":0,"content_reader_batches":5,"content_reader_unique_paths":30,"content_reader_file_events":30,"content_reader_bytes":sum(f["bytes"] for f in reads.values()),"repeated_project_content_reads":0,"distinction":"清单哈希在磁盘读字节，不构成模型内容理解；30份模型全文阅读来自5批 --read 的文本返回。规则文件和自生成日志另计，不伪装项目内容读。","log":"../read-log.jsonl"},
 "sources":source_records,"modules":modules,"infrastructure_and_materials":infrastructure,"key_connections":connections,
 "entry_map":{"public_route_mapping":{"POST /residents":"modules/residents/service.py:register","GET /catalog":"modules/catalog/service.py:list_saleable","POST /cart-lines":"modules/carts/service.py:put","POST /orders":"modules/orders/service.py:place","POST /orders/cancel":"modules/orders/service.py:cancel","POST /payments/capture":"modules/payments/service.py:capture","POST /picking":"modules/picking/service.py:complete","POST /packing":"modules/packing/service.py:complete","POST /shipping":"modules/shipping/service.py:dispatch","POST /delivery/confirm":"modules/delivery/service.py:confirm","POST /returns":"modules/returns/service.py:request","POST /returns/approve":"modules/returns/service.py:approve","POST /refunds":"modules/refunds/service.py:issue","POST /settlements/close":"modules/settlements/service.py:close"},"background":{"config":"project.json:job_handlers.maintenance","runner":"jobs/runner.py:invoke","handler":"modules/recovery/service.py:run","scheduler":"absent"}},
 "current_claims":claims,"claims_manifest":"claims.json","artifact_claim_links":{f:[c["claim_id"] for c in claims if any(t["path"]==f for t in c["targets"])] for f in ["analysis.md","chapter.md","flow.mmd","test-plan.md"]},
 "completed_artifacts":[{"path":"analysis.md","status":"完整静态画像、20模块覆盖、基础材料、关键连接、Design/Technical/Academic审查"},{"path":"chapter.md","status":"4.3 Markdown r1，静态事实审查及内置表达规则审查完成"},{"path":"flow.mmd","status":"FIG-43内容与源码和正文核对；图源完成；未渲染/查看/入稿"},{"path":"test-plan.md","status":"30项后续测试计划；全部未执行，可执行性待确认"},{"path":"claims.json","status":"稳定主张ID、全部来源指纹、来源定位与目标关联"},{"path":"checkpoint.json","status":"本接续记录"},{"path":"inventory-baseline.json","status":"首次wrapper清单原样保存"}],
 "phase_state":{"Evidence":"完成全部自有材料静态阅读","Design":"4.3蓝图见analysis.md，已按证据复核","Draft":"完成chapter.md r1","Technical_Review":"静态事实、条件、状态、边界核查完成，记录在analysis.md","Academic_Review":"遵循案例内academic-style规则，未读取全局技能","Final":"本轮六项产物完成；运行和图像/页面验收不在已完成范围"},
 "open_items":open_items,
 "resume_protocol":["先读checkpoint.json与当前用户任务，沿用确认定位/大纲，不重启访谈。","用同一受信wrapper --inventory取得当前完整路径集合与text-lf指纹，保存新报告但不覆盖基线。该哈希磁盘读取量与模型内容阅读单独登记。","按完整相对路径比较新增、删除、相同、变化；元数据相同不等于内容未变。相同指纹且已有充分模块记录者直接复用，不机械通读。","新增/变化入口先定向--read；若路径失效，依据新增文件指纹找重命名候选，候选仍要核角色，不能仅按文件名service.py合并。","从entry_map、modules、key_connections和claims.json找受影响来源/主张/正文段/流程节点/测试计划；变化只是needs_review提示，不宣告主张错误或全稿失效。","通过wrapper重读变化材料及必要调用方/被调方；逐条判定原主张仍成立、修订或证据不足。先保留未变更原有结论范围。","根据新任务授权定向更新有关成果，保留稳定主张ID和旧基线/复核记录；语义核查后再登记新来源指纹，不能自动接受全部变化。","若只更新4.3，最小复核集合取变化源+相应链路，未变完整模块地图可直接恢复；若新任务扩展模块，先看其已存职责/入口/规则，再按差距读必要内容。"],
 "next_minimal_read_set":{"without_changes":["artifacts/checkpoint.json","artifacts/claims.json","artifacts/chapter.md","artifacts/flow.mmd","artifacts/test-plan.md"],"project_content_when_unchanged":"无需重复读取；先wrapper清单比较。","if_order_changes":["modules/orders/service.py及发生变化的直接调用模块","store.py 若回滚含义变化","registry.py / project.json / jobs/runner.py 若入口配置变化"],"if_background_changes":["变化的maintenance绑定或处理函数","modules/orders/service.py:cancel仅在现存记录不足或接口变化时重读","modules/outbox/service.py与modules/notifications/service.py必要连接"],"rationale":"已保存完整20模块职责、规则与连接，以及30份来源指纹；后续读取由变化和新任务问题驱动。"}
}
write_json("checkpoint.json", checkpoint)

analysis = """# 项目画像与静态分析（r1）

## 范围、定位与读取基线

这是内部合成的社区订货配送案例，定位为计算机本科软件设计与实现，正式范围沿用 `thesis/positioning.md` 与 `thesis/outline.md`：本轮只撰写第四章4.3“订单创建与取消”。不重新访谈。修订为 `registry.py:REVISION = synthetic-shop-1.0`；没有取得Git提交/运行发布基线。

项目文件访问全部通过指定 `material_reader.py`：首次清单列30份文件，并对30份、22448字节做 text-lf SHA-256磁盘读取。该活动**不是模型内容阅读**。随后5批 `--read` 全文返回30份来源，模型据此核查20个业务模块以及10份入口/存储/配置/SQL/文档材料，无项目内容重复读、未覆盖项或实际排除项。原始返回为 `read-01-*.json` 至 `read-05-*.json`，首次清单保存在 `inventory-baseline.json`，操作记录为工作目录 `read-log.jsonl`。所有来源全文范围、完整指纹和关联主张见 `checkpoint.json:sources`。本轮没有执行、导入业务、安装依赖、联网或修改project。

清单默认会排除依赖/缓存/构建目录，但本次 `excluded/skipped/findings` 均为空；没有用这些常见名称替代真实性质核对。清单与读取不是原子快照；已核对本次内容阅读指纹与清单一致。后续必须比较新清单而不能把本记录当永久覆盖。

## 项目画像与材料类型

居民通过资料、商品目录和购物车形成单商户订单。订单先预留库存，记录本地账单、待入账积分和待投事件；本地付款记账后可进入拣货、包装、出库、交付。交付确认触发居民积分入账和商户待结算记录。退货申请/批准只建立售后记录，退款按本地已付余额登记。维护入口从配置获得，按订单创建时间清理仍预留的订单，再尝试发送本地事件。

主体为居民资料、商户标识及调用业务函数的调用方；材料没有居民身份认证、后台操作员角色、浏览器页面或HTTP服务。`registry.py` 中的路径只是14条函数映射，不能称为已部署API。业务链中只有字符串/ID及状态判断，区域相等判断不是身份认证。

执行模型是单进程内存 `Store`，拥有16个列表表及各自序号，订单行嵌在 `orders.lines`。`transaction` 对整个 `rows` 和 `sequence` 深拷贝，遇 `Exception` 恢复并重抛；不执行SQL，不提供并发锁、持久化或数据库隔离。独立 `schema.sql` 定义15张设计表，含 `customer_order.resident_id REFERENCES resident(id)`、`invoice.order_id UNIQUE` 和 `loyalty.order_id UNIQUE`；这些声明并未约束内存数据，不能将SQL `order_line` 与内存嵌套行混为一个已运行数据库。

证据类别：Python为静态实现；`project.json`为配置声明；SQL为设计草稿；README为背景声明；论文定位/大纲为已确认范围；没有测试源文件、执行报告、截图、真实用户研究、文献或性能材料。未执行的预期仅列测试计划。

## 全部业务模块覆盖

以下每行均为**已全文阅读并核实的静态实现**，不是凭目录或文件数推断覆盖。路径均相对project根；完整基线在checkpoint的同路径source中。无业务模块留为未读候选。

| 模块/完整来源路径 | 实际职责与入口 | 关键连接、规则和数据变化 | 主张与限制 |
| --- | --- | --- | --- |
"""
for m in modules:
    analysis += "| `"+m["source"]["path"]+"` | "+m["responsibility"]+"；"+"；".join(m["entries"])+" | "+"；".join(m["key_connections"]+m["confirmed_rules"])+" | "+", ".join(m["claim_ids"])+"；"+"；".join(m["open_items"])+" |\n"
analysis += "\n## 基础入口与其他材料覆盖\n\n| 完整路径 | 类型 | 已核实职责及边界 |\n| --- | --- | --- |\n"
for f in infrastructure:
    analysis += "| `"+f["path"]+"` | "+f["type"]+" | "+f["role"]+" |\n"
analysis += """
## 关键业务连接与状态

1. **创建链**：`registry.py:POST /orders → modules/orders/service.py:place → residents.require_active → carts.lines_for → catalog.require_saleable → pricing.subtotal → coupons.discount`。准备时确定单一商户、复制单价与配送区域；随后 `Store.transaction → inventory.reserve（逐行）→ orders.insert → invoices.create → loyalty.prepare → outbox.enqueue`，返回订单ID。交易内异常回滚全内存数据及序号；准备校验失败尚未写业务数据。见C-ORD-001/002/003、C-STORE-001。
2. **取消链**：`POST /orders/cancel → orders.cancel`，或配置后台 `recovery.run → cancel`。仅 `reserved` 接受取消；先 `inventory.release`，后写 `cancelled/cancelled_at`，若付款状态为 `captured` 再 `refunds.issue`，随后 `invoices.void`、`outbox.enqueue(order_cancelled)`。顺序使退款能够看到 `cancelled`；退款/账单失败会回滚先前释放与状态，非“部分取消成功”。取消不改pending积分，也没有操作者归属校验。见C-ORD-004/005/007/008。
3. **付款与履约链**：`payments.capture` 要求 `reserved/unpaid` 和总额相等，写付款账后变 `captured`；`picking.complete` 将 `reserved/captured → packing`，写 `picks.done`；`packing.complete` 在有done拣货且无已有包装时写 `packages.packed`，订单仍packing；`shipping.dispatch` 消耗reserved、置shipped、写in_transit运输单并排出库事件。到packing以后取消被拒绝。见C-PAY-001、C-FULFILL-001/002。
4. **交付与后账链**：`delivery.confirm` 对运输单状态和保存区域做判断，再要求订单shipped；快照内运输单和订单变delivered，`loyalty.grant` 将pending积分计入居民并改posted，`settlements.accrue` 生成商户pending账目。`settlements.close` 按merchant汇总pending并改booked，仅本地记账。见C-DELIVERY-001、C-LOYALTY-001、C-SETTLE-001。
5. **售后链**：`returns.request` 对delivered订单写requested，`returns.approve` 改approved；两者都不自动退款/回库。`refunds.issue` 允许cancelled订单或有approved退货记录的订单，按首条payment的余额累计退款，退尽才改payment_state=refunded；其公开入口没有自身transaction，也没有积分/结算冲销。见C-RETURN-001、C-REFUND-001。
6. **配置后台链**：`app.application → jobs.runner.task_registry(project.json)`；`job_handlers.maintenance → modules.recovery.service:run`，`jobs.runner.invoke`动态取函数并传repo/config/now/transport。`run`严格选择 `created_at < now-30*60` 且reserved的订单，不筛付款状态，按ID逐单取消，之后调用 `outbox.deliver_pending`。这条入口不来自前台菜单，材料没有调度器。取消异常中断本轮后续订单及投递，已经完成的前序订单取消不会被整体撤销。见C-ORD-006、C-RECOVERY-001。
7. **事件投递链**：创建/取消/出库写outbox的pending/attempts=0；维护选择pending且attempts<3，按ID取前20项，交 `notifications.send → 调用方transport.send`。成功变sent、次数加1；OSError只加1并保留pending。达到3次仍pending但不入选，返回值是选中尝试数，不是成功数。没有默认transport时会走OSError分支；非OSError未被该循环捕获。见C-OUTBOX-001、C-NOTIFY-001。

订单业务状态主干是 `reserved → packing → shipped → delivered`，仅 `reserved → cancelled`；付款状态独立为 `unpaid → captured → refunded（全额）`。包装状态属于packages而非新增订单状态。取消会释放reserved而出库会消耗reserved；不可把二者都写成“库存回滚”。退款和通知均为本地账目/调用机制，不能称为资金到账和消息送达的实测结果。

## 4.3章节蓝图（Evidence → Design）

| 正文稳定定位 | 解释任务 | 证据/主张 | 图/测试 |
| --- | --- | --- | --- |
| P43-01 | 创建/取消入口、主体和章节边界 | C-CONTEXT-001、C-ORD-001 | FIG-43；TP-01/12 |
| P43-02 | 居民、购物车、可售和单商户前置 | C-RES/CAT/PRICE/CART、C-ORD-001/002 | P1/P2；TP-02—06 |
| P43-03 | 小计、券归属/有效期/门槛/封顶 | C-COUPON-001、C-ORD-002 | P2；TP-07—09 |
| P43-04/05 | 库存—订单—账单—积分—事件顺序及内存回滚 | C-INV、C-ORD-003、C-STORE-001 | P3—PFAIL；TP-01/10/11 |
| P43-06/07 | 可取消状态、逐行释放、已付退款、账单作废、失败回滚 | C-ORD-004/005、C-REFUND、C-PAY | C0—CFAIL；TP-12—18 |
| P43-08/09 | 后台时限连接、事件传输边界、零额异常 | C-ORD-006/008、C-RECOVERY/OUTBOX/NOTIFY | M0—M4；TP-18—24 |
| P43-10 | 重复提交、未清数据、输入/权限/并发边界 | C-ORD-007、C-STORE-001 | TP-25—27 |

4.1负责完整服务组织与入口；4.2负责商品库存准备；4.4负责详细履约/售后/维护。本节只解释这些模块如何影响创建、取消和可取消状态，避免重复展开后续履约。

## Draft后技术审查

按源码逐项核了入口、主体、顺序、状态、异常和数据范围，并以稳定正文ID对照。P43-01/02不把resident_id当登录身份；P43-03保留到期等于now可用及金额门槛等于值可用；P43-04准确记录issued账单、pending积分和未发送事件；P43-05把transaction限制为内存快照；P43-06保留reserved且包含已付款的取消范围；P43-07按真实顺序先改cancelled再退款、退款失败恢复；P43-08不把配置handler写成已定时执行；P43-09不把尝试数当成功数，并保留零金额退款失败；P43-10保留取消积分不清、无幂等、无归属/数量复核的边界。

深度单独判断：主体/触发（P43-01/08）、条件/规则（P43-02/03/06）、处理链/分支（P43-04/07/08）、数据/状态（P43-04/06/07）、结果/异常（P43-05/09/10）、章节分工/依据（蓝图与claims）均已展开到可复述机制的层次；这不是运行正确性或论文等级认证。没有把“测试尚未执行”转成通过结果。

FIG-43内容核对：P1/P2覆盖创建准备拒绝；P3—P8顺序吻合；C2限制reserved；C3—C8保留释放、状态、条件退款、作废和入队顺序；PFAIL/CFAIL限定快照内异常；M1严格小于cutoff且不筛付款。维护分支为跨章节连接摘要，投递规则在正文和测试计划解释。图源未渲染、未导出查看、未入Word，不能称页面验收。

## 学术表达审查与本轮状态

遵循本案例 `rules/references/academic-style.md` 内置表达规则，未读取或声称调用全局academic-humanizer。先核事实再改表达：将“保证事务一致性/完成支付退款/自动推送”类可能误导的表述收敛为“快照恢复/本地记账/写入待投事件”；保留主体、条件、状态与失败出口；术语统一为预留、取消、本地账单、待入账积分、待投事件。正文不逐段堆源码审计语句。数值与边界没有在润色中变更。

本轮Evidence、Design、Draft、Technical Review、Academic Review及限定范围的交付已完成。运行验证、图源渲染查看、正式页面验收均未执行。完整未决项在checkpoint中按U-*登记，主要是执行证据缺失、外部适配器/认证缺失、零元已付款取消边界、取消pending积分保留、SQL草稿与内存实现分离。它们不会被隐藏为“全部测试通过”。

## 接续方法

新会话从 `checkpoint.json` 恢复定位、模块/入口/连接、30份来源指纹和稳定主张。先由受信wrapper取得新清单，按完整路径和text-lf SHA-256比较；新增/删失/变化仅提示复核。利用claims关联定位到P43段、FIG-43节点和TP用例，定向读取变化材料及必要调用连接；未变且记录充分的模块直接复用。语义核查之后才更新相关主张和基线，不能按文件变化自动判主张错误或刷新全部指纹。
"""
(OUT / "analysis.md").write_text(analysis, encoding="utf-8")
print(json.dumps({"sources":len(reads),"modules":len(modules),"claims":len(claims),"bytes_model_content_read":sum(f["bytes"] for f in reads.values()),"generated":["analysis.md","claims.json","checkpoint.json","inventory-baseline.json"]},ensure_ascii=False))
