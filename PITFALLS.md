# 实测陷阱字典（PITFALLS）

> 全部来自 2026-10-23 对 `https://mcp.mcd.cn` 的真实调用与 `tools/list` 实测，不是文档抄录。
> 每条都标了「现象 / 原因 / 正确做法」，附可复现手法。

---

## 1. 工具数量：文档写 33，实际 35

**现象**：按官方 README 的 33 个工具做规划，`tools/list` 却返回 35 个。

**多出来的两个**：
- `query-promotions` —— 企业团餐 `beType=6` 的满减/满折规则（只返原始规则，**不做最优推荐**）
- `query-survey-coupon` —— 按订单号查 **CSAT 满意度答卷** + 关联奖券核销状态

**复现**：`python doctor.py` 会打印实际数量并与基线比对。

**正确做法**：以 `tools/list` 为准；把工具列表当**运行时数据**而不是常量。

---

## 2. 官方文档把工具名写错了

**现象**：README §3 写 `query-partystore-date` / `query-partystore-session`，照着调 **404 / tool not found**。

**实际名字**（带连字符）：
- `query-party-store-date`
- `query-party-store-session`

**复现**：`python doctor.py` 会同时检查"文档名不存在"和"真实名存在"。

**正确做法**：所有派对工具按 `query-party-store-*` 拼；不要相信 README 的表格拼写。

---

## 3. 鉴权失败：状态码有**两种**，body 有**两种**，没有统一错误结构

**现象**：按文档写 `if resp.status == 401: 提示重新登录` —— 缺 Token 时根本走不到这个分支（拿的是 403），
而错 Token 时虽然进了分支，但 `resp.json()` 会直接抛异常（body 是纯文本）。

**实测**（2026-10-23，连测两轮结果一致）：

| 情况 | HTTP | Body |
|---|---|---|
| 未带 Token | **403** | 业务信封 `{"code":"0001","msg":"系统错误","data":null}` |
| Token 无效/失效 | **401** | 纯文本 `当前鉴权码不存在或已失效!`（**不是 JSON**） |
| Token 正常 | 200 | 标准 JSON-RPC |

⇒ 两处反直觉：
1. **缺 Token 是 403 不是 401** —— 很多客户端把 403 当"权限不足/被墙"，提示语会误导；
2. **两种失败的 body 形态完全不同**（业务信封 vs 纯文本），按同一套逻辑解析必然有一边炸。

**复现**：`python doctor.py --probe-auth`（会打印每次的真实 HTTP 状态码与 body 前缀）。

**正确做法**：状态码和 body 一起判，且要能容忍非 JSON ——

```python
# 1) 先按状态码分流（403 = 没带凭据，401 = 凭据无效）
if status in (401, 403):
    try:
        payload = json.loads(text)          # 403 是业务信封
        msg = payload.get("msg")
    except json.JSONDecodeError:
        msg = text.strip()                  # 401 是纯文本
    fail(msg)

# 2) 即使是 200，也要防业务信封（见第 1 条：有的路径直接回 code!=200）
elif isinstance(payload := safe_json(text), dict) and "jsonrpc" not in payload and "code" in payload:
    fail(payload.get("msg"))
```

---

## 4. `calculate-price` 传错字段会**静默返回 0 元**

**现象**：算价结果为 `price: 0`，无 error、无 warning，很容易误判成"该商品不可售"。

**一个常见原因**：`query-meals` 返回的商品标识字段叫 **`code`**，而 `calculate-price` 的
`items[].productCode` 要的是**同一个值、不同的字段名**。字段名传错就是 0。

**但 0 元不止这一种成因** —— 至少还有：`items` 为空数组、`quantity=0`、商品在该门店不可售、
`storeCode` 下压根没有这个商品。**所以别把"0 元"直接归因成字段名错**，否则排查方向会跑偏。

**正确做法**：先把 `code` 的值正确地喂给 `productCode`，再**带条件地**断言 ——
```python
items = [{"productCode": meal["code"], "quantity": 1}]   # 值来自 code，键名是 productCode

total = result["price"]
if total == 0 and items and not is_free_item:      # 免费的 0 元是合法的
    # 0 元且不免费 ⇒ 按上面的清单逐项排除，别直接下"下架"结论
    raise ValueError("算价为 0，需排查：字段名 / quantity / 门店是否可售")
```

---

## 5. 金额单位是「分」

**现象**：显示 5900、2048 之类的数字，误当元 → 价格放大 100 倍。

**实测样本**：派对场次 `{"price": 5900}` = **59 元/人**。

**正确做法**：所有金额 `/100` 后再展示。`calculate-price` 的文档里也明写"返回的价格字段单位为分"。

---

## 6. 特调（modification）必须"整组传"

**现象**：想做"去酱"却报错，或特调不生效。

**规则**：对于**包含 `unselectedKey` 的特调组**，该组内**所有**特调项都必须传：
- 用户**选中**的项 → `key` 用 `selectedKey`
- 用户**未选中**的项 → 若其 `unselectedKey` 非空，`key` 用 `unselectedKey`，**也必须传**

**正确做法**：从 `query-meal-detail` 拿到 `modification` 后，按组遍历全量传入，而不是只传用户改的那一项。

---

## 7. `query-store-coupons` 和 `query-my-coupons` 不是一回事

| 工具 | 语义 |
|---|---|
| `query-my-coupons` | 你卡包里的券。**明确声明不做门店/渠道校验，"不承诺可用于当前订单"** |
| `query-store-coupons` | **指定门店 + 订单类型**下真正可用的券 |

**现象**：用前者判断"这单能用哪张券" → 给出不可用推荐，下单时才发现券不能用。

**正确做法**：要判断当前订单可用券，必须用 `query-store-coupons`。

---

## 8. 到店自取的 `beCode` 不能传

**现象**：`beType=1`（到店自取）时传了 `beCode`，接口报错。

**规则**（四个场景的组合是固定的）：

| beType | orderType | beCode |
|---|---|---|
| 1 到店自取 | 1 | **不传** |
| 5 得来速 | 1 | **必传**（来自 `query-nearby-stores`） |
| 2 麦乐送 | 2 | **必传**（来自 `delivery-query-stores`） |
| 6 企业团餐 | 2 | **必传**（来自 `delivery-query-stores`） |

**正确做法**：把这张表写成代码里的一个函数，不要靠记忆。

---

## 9. 积分兑换的多商品必须"排队"

**现象**：一次兑换多个商品，部分失败。

**规则**：`mall-create-order` 单个商品一单；多商品**必须分别下单，且等前一单返回成功后再发下一单**（不能并发）。

**正确做法**：串行 + 每单校验 `status`（1 全成功 / 2 部分成功 / 0 失败）。

---

## 10. `order-list` 只有最近 10 单

**现象**：想拉全部历史做统计，只能拿到 10 条。

**正确做法**：`order-list` 无分页参数；需要更多历史用 `mall-order-list`（`lastId` + `size`，单页 ≤10），或引导用户去 APP 看。

---

## 11. 主题派对商品不一定在「主题类派对」类目里

**现象**：按 `catRuleIds=1>6>21`（主题类派对）找"程序员节派对"，**找不到**。

**实测**：它挂在 **`1>6>25`（品鉴会）**，`spuName="程序员节派对"`，`spuId=18229`，¥59。

**正确做法**：`mall-points-products` **不传 `catRuleIds`** 拉全量，再按名字匹配；或先 `mall-product-detail` 确认 `categoryRuleId`。

---

## 12. 限流是 600 次/分钟，但有独立频控

- 主接口：600 次/分钟/Token，超限 `429`。
- **`draw-lottery` 另有频控**：短时间重复调用返回"操作太频繁，请稍后再试"，**不扣积分**。
- 官方曾在 2026-01 出现过"一天调一次的 Token 也被限流"的平台 bug（已修复）。

**正确做法**：批量场景加退避重试；抽奖不要做自动重试。

---

## 13. `list-nutrition-foods` 的 `data` 是**字符串**，不是数组

**现象**：以为拿到的是 `[{productName, energyKcal, ...}, ...]`，结果 `data` 是一整段文本，`json.loads` 后仍然是 `str`，遍历就报错或拿到空。

**实测返回结构**（2026-10-23）：

```json
{
  "success": true,
  "code": 200,
  "data": "[160]{productName,nutritionDescription,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n  猪柳麦满分,null,1288,308,16,16,24,781,213\n  中薯条,null,1210,289,4,12,38,165,18\n  ..."
}
```

- `data` 类型是 **string**（`json.loads` 之后仍是 `str`，别直接当数组遍历）；
- 开头 `[160]` 是**声明条数**，`{...}` 是字段名列表，`:` 之后是数据行；
- 每行 `,` 分隔，字段顺序与 `{}` 内一致；
- `nutritionDescription` 常为 `null`，个别行是"能量约清水1杯"这类**自由文本**。

**关于上面两条的实测依据**（2026-10-23 当场数的，不是从格式推的）：

| 检查项 | 结果 |
|---|---|
| 声明条数 `[160]` vs 实际非空行数 | **160 vs 160，一致** |
| 字段数匹配的行 | **160 / 160，全部匹配** |
| 字段数不匹配的行 | **0** |

⇒ 本次数据里"逗号切分 + 顺序一致"是成立的。**但 `nutritionDescription` 是自由文本**，
一旦某行描述里出现逗号，行就会被切成比字段更多的段 —— 所以解析必须按字段数校验，
并且**把丢弃的行计数报出来**，不要静默丢掉（静默丢行会让"160 条"悄悄变成 158 条）。

**正确做法**：

```python
import json, re
raw = resp["data"]
if isinstance(raw, str):
    head, _, body = raw.partition(":")
    declared = int(re.search(r"\[(\d+)\]", head).group(1))
    fields = re.search(r"\{(.+?)\}", head).group(1).split(",")

    rows, dropped = [], 0
    for line in body.strip().splitlines():
        cells = [c.strip() for c in line.split(",")]
        if len(cells) == len(fields):
            rows.append(dict(zip(fields, cells)))
        elif line.strip():
            dropped += 1                    # 别静默丢：自由文本含逗号就会到这里

    if dropped or len(rows) != declared:
        print("警告：声明 %d 条，解析出 %d 条，丢弃 %d 行（字段数不匹配）"
              % (declared, len(rows), dropped))
```
```

**同类提醒**：不要因为 `data` 长得像 JSON 就假设它是对象 —— 先 `type()` 一下。

---

*以上每条都能用本仓库的 `doctor.py` / `mcd_mcp.py` 复现。*
