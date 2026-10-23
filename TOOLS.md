# 麦当劳 MCP 工具速查（35 个，实测于 2026-10-23）

> 由 `tools/list` 真实返回生成，非文档抄录。官方 README 只列 33 个。

> 标记：标注"写"= 有副作用（下单/扣积分/领券/加地址），其余为只读。


## 门店与菜单（5）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `now-time-info` | 只读 | `—` | 获取当前时间信息 - 返回当前服务器的完整时间信息，包括： - 时间戳（毫秒级） - 格式化的日期时间 - 年月日信息 - 时区和UTC时间 在你不知道当前时间，并且用户需要指定日期查询活动日历的时候有用 |
| `query-meal-detail` | 只读 | `storeCode, orderType, beType, code` | Description: 餐品详情, 支持到店自提(orderType=1)和外送(orderType=2)两种场景 When: - 用户想要了解餐品有哪些组成 - 用户想要更换套餐的组成或者更换特制商品 Input:  |
| `query-meals` | 只读 | `storeCode, orderType, beType` | Description: 餐品列表, 支持到店自提(orderType=1)和外送(orderType=2)两种场景 企业团餐场景下，可按照这个规则给用户进行搭配 - **20元以下**: 小食 - **20-30元** |
| `query-nearby-stores` | 只读 | `beType, searchType` | Description: 到店场景下，查询用户可点餐门店，需要用户明确是到店自取还是车道取餐 - beType=1(到店自提): 返回的门店无 beCode，后续工具调用不传 beCode - beType=5(得来速) |
| `query-store-coupons` | 只读 | `orderType, beType, storeCode` | Description: 查询【指定门店+订单类型】下可使用的优惠券，支持到店(orderType=1,含到店自取和得来速)和外送(orderType=2,含麦乐送和团餐) When： - 当用户已获取到门店时，用户询问 |

## 算价与下单（5）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `calculate-price` | 只读 | `storeCode, orderType, beType` | Description: 计算商品的价格（含优惠），支持到店自提(orderType=1)和外送(orderType=2)两种场景 When： - 用户问"这些商品多少钱" - 用户问"总价是多少" Input: - r |
| `cancel-order` | 写 | `orderId, cancelReasonCode` | Description: 取消订单，非商城订单 When： - 用户说"取消订单"、"我要取消" - 用户说"帮我取消一下订单" Input: - cancelReasonCode: 取消原因code，必填，可选值：1= |
| `create-order` | 写 | `storeCode, orderType, beType` | Description: 创建麦当劳订单，支持到店(orderType=1)和外送(orderType=2)两种场景下单, 必须先确定订单类型，必填 (1：到店，2外送) When： - 用户说"我要下单" - 用户说" |
| `order-list` | 只读 | `—` | Description: 查询麦当劳历史订单，非商城订单，商城订单需要使用mall-order-list When： - 用户询问"帮我查询一下历史订单" - 用户询问"我买了什么麦当劳餐品" |
| `query-order` | 只读 | `orderId` | Description: 查询订单详细信息 When： - 用户询问"查下订单详情"、"订单状态"、"我的订单" - 用户提供了麦当劳订单编号想查询配送进度 - 用户说我已支付或者支付失败时，查询一下最新的订单状态 |

## 外送与团餐（5）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `delivery-create-address` | 写 | `address, addressDetail, city, contactName, phone` | Description: 创建用户配送地址 When： - 用户想添加新的配送地址 Input: - city: 城市名称，必填，必须从用户输入中获取实际城市名称，如"南京市" - contactName: 联系人姓名， |
| `delivery-query-addresses` | 只读 | `—` | Description: 外送场景下，查询用户配送地址列表 When： - 用户想点麦乐送 - 用户想吃麦当劳，并配送到家 - 我想点团餐 Next： - 1:引导用户创建新的配送地址 - 2:当用户选择企业团餐时，需要 |
| `delivery-query-stores` | 只读 | `beType, addressId` | Description: 外送场景下，用户选择完地址后，需要根据地址ID，查询用户当前地址可配送的门店 When: - 外送场景下，用户选择完配送地址后 - 用户问"这个地址能送到哪些店" 注意：到店场景请使用 quer |
| `query-meal-assistance` | 只读 | `storeCode` | Description: 仅支持企业团餐场景(beType=6)在calculate-price前需要获取当前门店可用的助餐服务 When： - 企业团餐场景(beType=6)下，用户选完商品后、计算价格前 - 用户问 |
| `query-promotions` | 只读 | `storeCode, orderType, beType` | Description: 查询当前门店企业团餐场景下可用的促销规则（满减/满折），仅返回当前时间有效且适用在售餐品的规则原始数据 When： - 企业团餐场景(beType=6)下，用户搭配方案前需要了解当前门店有哪些可 |

## 券与积分（4）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `auto-bind-coupons` | 写 | `—` | 自动领取麦麦省所有当前可用的麦当劳优惠券。无需指定具体的优惠券和couponId，系统会自动领取用户可领的所有券。当用户说"帮我领券"、"自动领取优惠券"、"一键领券"时使用此工具。 |
| `available-coupons` | 只读 | `—` | 查询用户当前可领取的麦麦省的优惠券列表。返回券名称、图片、状态和促销标签。当用户询问有什么优惠、可以领什么券时使用此工具。 |
| `query-my-account` | 只读 | `—` | 查询用户积分账户详情 - 当用户询问"我有多少积分"、"查下我的积分"、"积分余额"、"查询过期积分"时使用 |
| `query-my-coupons` | 只读 | `—` | 获取用户卡包中的优惠券资产信息，用于“我有什么券 / 券详情查看”等展示与管理场景。 注意：该接口返回的是用户拥有的券，不进行门店、渠道、配送方式等下单规则校验，因此不承诺可用于当前订单。 若业务目标是“当前门店/当前订 |

## 积分商城（5）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `mall-create-order` | 写 | `skuId, spuCategory` | 创建积分兑换订单，仅支持shopId=2（从 mall-product-detail 获取） - 当用户询问"用积分兑换这个商品"、"兑换这个券"、用户确认兑换商品时使用,切记：如果单个商品一个订单下单；如果用户需要兑换 |
| `mall-order-detail` | 只读 | `orderId` | Description: 查询麦麦商城订单详情 When： - 用户询问"麦麦商城的订单详情" Next: - 引导用户："您可以打开麦当劳APP查看凭证等其他信息" |
| `mall-order-list` | 只读 | `—` | Description: 查询麦麦商城订单列表 When： - 用户询问"查看我的麦当劳商城订单列表" |
| `mall-points-products` | 只读 | `—` | 查询可兑换餐品券列表 - 当用户询问"有哪些积分兑换商品"、"积分可以兑换什么"、"查看积分商城"时使用 支持类目规则筛选：商品券(1>4)、实物商品(2)、周边产品(2>8)、实物礼品卡(2>9)、生日类派对(1>6> |
| `mall-product-detail` | 只读 | `spuId` | 查询积分兑换商品详情 - 当用户询问"这个商品详情是什么"、"查看商品详细信息"、用户点击商品查看详情时使用 返回商品的所有SKU规格信息，用户需要选择具体SKU后才能下单兑换  前提条件： - 已知商品SPU ID，需 |

## 主题活动/派对（5）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `party-order-create` | 写 | `partyType` | Description: 创建生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动, 仅支持shopId=5（从 mall-product-detail 获取）的调用，   支持包场(partyType=1) |
| `query-party-city` | 只读 | `spuId` | Description: 活动派对商品配置场次城市列表, 必须先确定spuId(从 mall-points-products 获取）或查询商品详情（从 mall-product-detail 获取) When： - 用户 |
| `query-party-store` | 只读 | `code` | Description: 查询指定城市下支持主题派对的门店列表。当用户选择了城市后，需要查看该城市有哪些门店可举办生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动时使用 Preconditions： -  |
| `query-party-store-date` | 只读 | `spuId, storeCode` | Description: 查询指定门店支持生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动的可预约日期列表。当用户选择了门店后，需要查看该门店哪些日期可预约时使用。 When： - 用户询问"这家店哪天可 |
| `query-party-store-session` | 只读 | `spuId, storeCode, dateStr` | Description: 查询指定门店、指定日期下的生日类派对/主题类派对/麦麦体验营/品鉴会/读书会/积分兑换活动场次列表。当用户选择了日期后，需要查看当天有哪些场次可预约时使用。 When： - 用户询问"查看主题活 |

## 积分抽奖（3）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `draw-lottery` | 写 | `—` | Description: 使用后台配置的抽奖消耗规则参加一次当前积分抽奖并返回结果，服务端原子完成次数或积分扣减与抽奖。 重要约束：仅能在向用户展示 query-lottery-info 返回的 drawDecision |
| `query-lottery-info` | 只读 | `—` | Description: 查看当前积分抽奖活动信息，包括活动基本信息、抽奖消耗规则、单次所需积分、剩余可抽次数、当前可用积分与公开奖品列表，不执行抽奖。 When： - 用户询问"积分抽奖有什么奖品" - 用户询问"抽一 |
| `query-my-prizes` | 只读 | `—` | Description: 查询当前登录会员通过积分抽奖获得的本期及历史奖品（可用/已使用/已过期/已领取/已失效）。 When： - 用户询问"我抽中了什么奖品" - 用户询问"我的奖品还有哪些能用" - 用户询问"查我 |

## 满意度（1）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `query-survey-coupon` | 只读 | `orderId` | Description: 按订单号查询当前 MCP 用户本人订单的 CSAT 满意度答卷，并返回该订单关联奖券的标题、核销时间、核销状态和点餐方式。 When: 用户询问某个订单的满意度答卷结果时使用；用户询问某个订单关 |

## 营养（1）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `list-nutrition-foods` | 只读 | `—` | 获取麦当劳常见餐品的营养成分数据，包括能量、蛋白质、脂肪、碳水化合物、钠、钙等信息，当用户咨询麦当劳餐品的热量、营养，帮助用户搭配指定热量套餐时有用 |

## 其他（1）

| 工具 | 读写 | 必填参数 | 说明 |
|---|---|---|---|
| `campaign-calendar` | 只读 | `—` | 查询麦当劳中国当月的营销活动日历，返回进行中、往期和未来日期的活动。适用于查看用户进行中和即将到来的可参与活动，还可查询用户对活动的订阅状态。 When：   - 用户问"最近有什么活动"、"这个月有什么优惠活动"、"有 |
