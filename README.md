# mcd-mcp-kit

> 麦当劳中国 MCP Server 的**接入体检工具包** —— 30 秒确认你的接入到底通没通，以及为什么"看起来通了"其实是错的。


---

## 为什么需要它

接入麦当劳 MCP 的第一小时，几乎每个人都会踩同样的坑：

| 你可能以为 | 实际是 |
|---|---|
| 文档列了 33 个工具 | `tools/list` 返回 **35** 个，多出的两个文档没写 |
| 鉴权失败会统一返回 `401` | **两种状态码、两种 body**：无 Token → `403` + 业务信封 `code=0001`；错 Token → `401` + **纯文本**（不是 JSON） |
| 照文档写 `query-partystore-date` | 正确名字是 `query-party-store-date`，照抄调用必失败（返 JSON-RPC error，**不是 404**） |
| 算价返回 0 元 = 商品不可售 | 是字段名传错了（`code` vs `productCode`），**接口不报错** |
| 价格 5900 = 5900 元 | 单位是**分**，= 59 元 |
| `query-my-coupons` 能判断这单能用哪张券 | 不能，它**不做门店校验**；要用 `query-store-coupons` |

`doctor.py` 把这些一次性检查完，并给出一份可直接粘贴进 issue 的报告。

---

## 快速开始（30 秒）

```bash
# 1. 拿 Token（手机号登录 → 控制台 → 激活）
#    https://open.mcd.cn/mcp

# 2. 设置环境变量
set MCD_MCP_TOKEN=你的token            # Windows cmd
export MCD_MCP_TOKEN=你的token         # macOS / Linux
$env:MCD_MCP_TOKEN="你的token"         # PowerShell

# 3. 体检
git clone https://github.com/CRFXN5C/mcd-mcp-kit.git
cd mcd-mcp-kit
python doctor.py
```

**零依赖**：只用 Python 标准库，不需要 `pip install`。

---

## 真实输出

`python doctor.py --probe-auth` 的实际输出（2026-10-23）：

```
=== 麦当劳 MCP 接入体检 ===

[ OK ] MCD_MCP_TOKEN  已设置（长度 32）
[INFO] 无 Token 时    HTTP 403 | 业务 code=0001 | body 前缀='{\n  "code" : "0001",\n  "msg" : "系统错误",\n '
[INFO] 错 Token 时    HTTP 401 | body='当前鉴权码不存在或已失效!'（不是 JSON，别只判 401）
[ OK ] initialize     已连通 | 服务 mcd-mcp 1.0.0 | 协商协议 2025-06-18
[ OK ] tools/list     返回 35 个工具（基线 35）
[ OK ] 文档命名       query-partystore-date 不存在（官方 README 写错，正确名是 query-party-store-*）
[ OK ] 文档命名       query-partystore-session 不存在（官方 README 写错，正确名是 query-party-store-*）
[ OK ] 真实命名       query-party-store-date
[ OK ] 真实命名       query-party-store-session
[INFO] 写操作         当前可用的 7 个写操作：auto-bind-coupons, cancel-order, create-order,
                      delivery-create-address, draw-lottery, mall-create-order, party-order-create

结论：可以正常使用（7 项通过 / 0 项警告 / 0 项失败）
```

> 断网、拒连、DNS 失败这类情况不会抛 traceback —— 已经收集到的结果照常打印，
> 失败项给出最近一次错误原文，退出码 `2`。

---

## 三个命令

| 命令 | 作用 |
|---|---|
| `python doctor.py` | 接入体检（只读，无副作用） |
| `python doctor.py --probe-auth` | 额外探测「无 Token / 错 Token」的真实状态码与 body 形态 |
| `python doctor.py --json` | 机器可读输出，便于接 CI |

> `doctor.py` 退出码：`0` = 全部通过（可能有 WARN）；`2` = 存在问题（有 FAIL）。
> 参数写错时 `argparse` 也返回 `2`，若要在 CI 里区分，请用 `--json` 读 `ok` 字段。

配套的最小客户端 `mcd_mcp.py`：

```bash
python mcd_mcp.py tools                              # 列全部 35 个工具
python mcd_mcp.py call now-time-info                 # 调只读工具
python mcd_mcp.py call now-time-info --json-only     # 只看原始 JSON，跳过字段说明
python mcd_mcp.py demo                               # 跑一遍只读演示
python mcd_mcp.py raw                                # 排错：打印握手原始 HTTP 头
```

> 服务端会把「字段说明 + 原始响应」拼在同一段文本里返回，`--json-only` 只保留后者，方便接管道或 `jq`。
> `mcd_mcp.py` 已内置两种非标准错误形态的处理，退出码：`0` 正常 / `1` 用法错 / `2` 鉴权或协议失败。

---

## 仓库结构

```
mcd-mcp-kit/
├── doctor.py                 # 接入体检（本项目主体）
├── mcd_mcp.py                # 零依赖最小客户端（Streamable HTTP + JSON-RPC）
├── TOOLS.md                  # 35 个工具速查表（由 tools/list 真实生成）
├── PITFALLS.md               # 13 条实测陷阱字典 ← 最有价值的部分
├── MCP_INTEGRATION.md        # 实际调用了哪些 Server/Tool、调用流程、业务价值
├── mcp-config.example.json   # 脱敏配置示例（仅环境变量占位符）
├── CONTEST_DECLARATION.md    # 参赛声明
├── LICENSE                   # MIT
├── .gitignore
└── README.md
```

---

## 13 条实测陷阱（摘要）

完整版见 **[PITFALLS.md](./PITFALLS.md)**，每条都带「现象 / 原因 / 正确做法 / 复现方式」。

| # | 坑 |
|---|---|
| 1 | 工具数 33 vs 35（`query-promotions`、`query-survey-coupon` 文档没写） |
| 2 | 文档工具名拼错：`query-partystore-*` → `query-party-store-*` |
| 3 | 鉴权失败**状态码有两种**：无 Token `403` + 业务信封、错 Token `401` + 纯文本（没有统一错误结构） |
| 4 | `calculate-price` 字段名传错 → **静默 0 元**（但 0 元不一定是传错，别只归因这一条） |
| 5 | 金额单位是**分** |
| 6 | 特调 `modification` 必须整组传（`selectedKey` / `unselectedKey`） |
| 7 | `query-store-coupons` ≠ `query-my-coupons`（后者不校验门店） |
| 8 | 到店自取（`beType=1`）**不能传** `beCode` |
| 9 | 积分兑换多商品必须**串行排队**下单 |
| 10 | `order-list` 只有最近 **10** 单 |
| 11 | 主题派对商品可能在「品鉴会」类目（`1>6>25`），不在主题类派对 |
| 12 | 抽奖有独立频控，且**不要**自动重试 |
| 13 | `list-nutrition-foods` 的 `data` 是**字符串**（内含 `[160]{字段列表}:` + CSV 行），不是数组 |

---

## 35 个工具

见 **[TOOLS.md](./TOOLS.md)**（按业务域分组，标注读写与必填参数）。

一句话概括：**28 个只读 + 7 个有副作用**，覆盖门店菜单、算价下单、外送团餐、券与积分、积分商城、主题活动/派对、积分抽奖、满意度、营养。

> 注意：7 个写操作（下单/取消/兑换/派对/领券/抽奖/加地址）会真实产生费用或消耗积分。本项目**只读优先**，不自动下单。

---

## 设计原则

1. **只读优先** —— `doctor.py` 全程不产生订单、不扣积分、不领券。
2. **零依赖** —— 只用标准库，避免"装环境"劝退。

---

## 备注

- 本项目为**麦当劳程序员创意开发大赛**参赛作品，由作者独立开发，**非麦当劳官方产品**。
- 工具数量与命名以 2026-10-23 实测为准；服务端迭代后请更新 `doctor.py` 里的 `EXPECTED_TOOLS`。

---

## License

MIT
