# 4.3后续测试计划（r1，未执行）

对象为 `synthetic-shop-1.0` 的单进程内存机制。以下全部是**待执行计划**，预期由静态源码推导，未安装、导入或执行项目，也没有通过数量或通过率。测试可执行性须在后续具备授权、环境及夹具后确认。源码、指纹与正文/图节点关联见 `claims.json`。

## 后续准备与观察口径

后续先确认解释器、项目模块装载和可信夹具可用，再决定直接函数测试或受控驱动方式；不把字符串路由当成现成HTTP服务器。每例创建独立Store，使用伪造居民/商品/券/库存等数据，不连接外部支付、物流或真实通知服务。正常基础数据建议：活动居民R1，zone为Z1，points为0；单商户M1；商品A单价1200分、数量2，商品B单价500分、数量1；两行可用库存均充足、预留均为0。无券小计2900分、预备积分29。商品、库存、券没有完整管理入口，夹具如何写入须后续确认；不能先称“测试环境已具备”。

冻结逻辑时间 `now=10000` 供边界比较；默认30分钟对应cutoff=8200。比较异常前后的整个 `repo.rows` 和 `repo.sequence`，异常后重新通过repo取行，避免拿已被快照替换的旧行引用作断言。错误类型/消息、返回值、订单/付款/账单/积分/事件记录及各库存计数均留存实际原始输出；失败注入只在后续测试夹具或替身中进行，不改业务源码。需要传输时只用记录发送内容或按次抛OSError的可控替身。

| 用例ID | 前置与操作 | 待验证预期（不是实际结果） | 关联主张 |
| --- | --- | --- | --- |
| TP-01 | 基础两商品同商户、无券，调用place | 返回新订单ID；总额2900；两行available分别减2/1、reserved加2/1；订单reserved/unpaid且复制Z1、M1与单价；账单issued/2900、积分pending/29，居民points仍0；创建事件pending/0；购物车不清 | C-ORD-001/002/003、C-INV-001、C-LOYALTY-001 |
| TP-02 | 分别使用缺失居民或active=False居民调用place | require_active抛ValueError；所有写表和序号不变 | C-RES-001、C-ORD-001 |
| TP-03 | 空购物车调用place；另用put传0、负数、非int数量 | 空车拒绝；put拒绝各非法数量且不写行；place没有独立数量再校验，另见TP-27 | C-CART-001、C-PRICE-001、C-ORD-001 |
| TP-04 | 商品缺失或saleable=False；另调用freeze后创建 | 创建拒绝且库存/订单等不变；freeze后商品不再通过可售判断 | C-CAT-001、C-ORD-001 |
| TP-05 | 将B的merchant_id设为M2再place | 抛one merchant per order；没有库存预留和订单写入 | C-ORD-001/002 |
| TP-06 | 将商品单价设为0、负数、浮点数或bool，分别place | 正整数单价检查拒绝；所有写表不变；保留原始错误 | C-PRICE-001、C-ORD-002 |
| TP-07 | 小计2900；券归R1、活动、门槛2900、到期10000、抵扣300；调用place | 门槛相等且到期等于now可用；总额2600；积分pending/26；券字段不变 | C-COUPON-001、C-ORD-002 |
| TP-08 | 分别缺券、券归他人、停用、到期9999、门槛2901 | 各拒绝且无库存/订单写入；与TP-07精确比较边界 | C-COUPON-001 |
| TP-09 | 抵扣券额大于或等于2900且其他条件满足，place | 抵扣封顶为2900，总额0、积分0、账单0；初始仍reserved/unpaid；后续零元付款取消见TP-18 | C-COUPON-001、C-ORD-008 |
| TP-10 | A可预留而B库存不足或缺库存，place；按创建前快照核查 | A已发生的预留被恢复；orders/invoices/loyalty/outbox及所有序号不新增；异常抛出 | C-STORE-001、C-ORD-003、C-INV-001 |
| TP-11 | 后续受控替身分别在invoices.create、loyalty.prepare或outbox.enqueue处抛Exception，执行place | 订单、此前库存和账目全部恢复到进入快照前，包括sequence；保存实际注入点和输出 | C-ORD-003、C-STORE-001 |
| TP-12 | TP-01形成unpaid预留订单，cancel(now) | 返回cancelled；逐行库存回到创建前；status=cancelled、cancelled_at=now、payment_state仍unpaid；账单void；新增取消事件；无付款/退款记录 | C-ORD-004、C-INVOICE-001 |
| TP-13 | 预留订单按总额capture后cancel | 本地payment amount=2900/refunded=2900；新增refund 2900；订单cancelled/refunded；库存释放、账单void、取消事件入队；不主张外部资金到账 | C-PAY-001、C-ORD-005、C-REFUND-001 |
| TP-14 | 缺单、已cancelled重复取消，以及拣货进入packing后分别cancel；其他非reserved状态同样检查 | 均拒绝；无再次库存释放或重复退款/事件；picking要求reserved/captured且先写done再packing | C-ORD-004、C-FULFILL-001 |
| TP-15 | 造captured但缺付款、退款可用余额不足等异常账目，cancel | 退款校验拒绝；取消整体回滚到原reserved/captured及原库存、账单、事件/序号；异常数据不能当正常可达业务状态 | C-ORD-005、C-REFUND-001、C-STORE-001 |
| TP-16 | 取消多行订单时A预留充足而B预留不足/缺行 | 后行release失败，A已释放量与所有状态恢复；不写取消事件 | C-INV-001、C-ORD-004、C-STORE-001 |
| TP-17 | 预留订单的账单缺失，cancel；另在最终取消事件入队处注入Exception | 账单缺失/入队错误使先前释放、cancelled状态和可能退款全部恢复；序号恢复 | C-INVOICE-001、C-ORD-004、C-STORE-001 |
| TP-18 | TP-09零元订单capture(0)，再cancel | capture的相等检查允许记0并改captured；取消退款金额0被正数判断拒绝，取消回滚为reserved/captured，原预留和issued账单仍在；不是正常取消通过 | C-ORD-008、C-PAY-001、C-STORE-001 |
| TP-19 | 经配置task_registry/invoke触发maintenance（后续可执行性确认）；reserved订单created_at依次8199/8200/8201；now=10000 | 只8199被选择取消；8200相等和8201较新均保留；验证实际处理函数来自job_handlers绑定，不假定自动调度 | C-RECOVERY-001、C-ORD-006 |
| TP-20 | 同为8199的unpaid和captured预留订单，另有过期packing订单，运行maintenance | 两个reserved均进入取消，captured走退款；packing不处理；返回cancelled按ID升序 | C-ORD-006、C-RECOVERY-001 |
| TP-21 | 创建事件与取消事件pending/0，maintenance使用成功传输替身 | 取消循环后尝试投递；记录order_id及匹配模板文本；成功事件sent/1；notification_attempts表示选中数量 | C-OUTBOX-001、C-NOTIFY-001、C-ORD-006 |
| TP-22 | 准备超过20条eligible事件，并混入sent与attempts=3的pending事件 | 每次至多选ID最小的20条eligible；sent和已达3次项不选；未选项不改 | C-OUTBOX-001 |
| TP-23 | transport=None或替身抛OSError，分批重复maintenance投递；另观察非OSError | OSError仅增加attempts并留pending；到3次后仍pending且不再选。非OSError不被该捕获处理，保留实际中断位置，不写“所有异常均重试” | C-OUTBOX-001、C-NOTIFY-001 |
| TP-24 | 多个过期reserved订单按ID排，首单正常、第二单缺账单导致cancel异常，后续另有订单和事件 | 首单已取消保留；第二单自身快照恢复；后续订单与投递不再执行；没有全批回滚 | C-RECOVERY-001、C-STORE-001 |
| TP-25 | 后续确认cancel仅参数order_id/now，无调用人；用另一个调用方概念提交同订单ID | 不应期待“非本人必拒绝”的安全断言；静态入口不校验归属，实际观察须单列为边界，不能标鉴权通过 | C-ORD-007 |
| TP-26 | 已创建积分pending订单取消，读取loyalty与resident | pending记录留存、points不因取消改变；不能期望自动撤销积分；非delivered订单调用grant应拒绝 | C-ORD-007、C-LOYALTY-001 |
| TP-27 | 同购物车与同券连续place且库存充足；另以测试夹具直接写非法数量行 | 连续调用会另建订单、再预留，购物车/券不消费；非法数量在place无专门再校验，其具体异常/计数变化需运行记录，不预设为拒绝 | C-ORD-007、C-CART-001、C-PRICE-001、C-COUPON-001 |
| TP-28 | 分别金额不匹配、重复capture及非reserved订单capture | 拒绝付款记账，不新增payments或改变状态；不将此断言扩为支付网关联调成功 | C-PAY-001 |
| TP-29 | 正常付款→拣货→包装→出库→区域匹配交付；另错区域/状态 | 拣货改packing；包装只写packed；出库消耗预留、shipped/in_transit及事件；交付改delivered、积分posted及居民加分、结算pending。错条件拒绝；只作为4.3状态边界的补充回归计划 | C-FULFILL-001/002、C-DELIVERY-001、C-LOYALTY-001、C-SETTLE-001 |
| TP-30 | delivered订单申请/批准退货，单独退款，再按商户close；记录前后账目 | 申请/批准不自动退款回库；approved允许按余额退款；该链不冲销积分/结算；close将pending记booked并返回汇总额，非银行划款。扩展用例属于4.4边界，仍未执行 | C-RETURN-001、C-REFUND-001、C-SETTLE-001 |

## 后续执行记录格式

每项记录：执行批次、源码修订与来源指纹、环境/夹具、用例ID、操作、预期、实际输出与状态差异、通过/失败/阻塞、原始记录路径。现阶段所有用例统一状态为“未执行；可执行性待确认”。若后续材料改变，先复核相应主张与预期，再执行；不得将计划预期直接写入“实际”列。
