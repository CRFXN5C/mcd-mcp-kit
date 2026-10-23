# MCP 集成说明

本项目实际接入并真实调用了**麦当劳中国 MCP Server**，以下是 Server、Tool、调用流程与业务价值的说明。

---

## 1. 接入的 MCP Server

| 项 | 值 |
|---|---|
| 名称 | 麦当劳中国 MCP Server（`mcd-mcp`） |
| 端点 | `https://mcp.mcd.cn` |
| 传输 | Streamable HTTP（JSON-RPC 2.0，响应可能是 JSON 或 SSE） |
| 协议版本 | `2025-06-18` |
| 鉴权 | `Authorization: Bearer <MCD_MCP_TOKEN>`，Token 从环境变量读取 |
| 服务端标识 | `serverInfo: mcd-mcp 1.0.0`，`capabilities: tools` |
| 限流 | 600 次/分钟/Token |

## 2. 实际调用的 Tool

### 2.1 协议方法（所有功能的基础）

| 方法 | 用途 |
|---|---|
| `initialize` | 握手，拿到 `serverInfo` / `protocolVersion` / `capabilities` |
| `notifications/initialized` | 握手后的完成通知 |
| `tools/list` | **本项目的核心数据源**：获取全部 35 个工具的名称、描述、`inputSchema` |

> `doctor.py` 的体检结论**以 `tools/list` 的实时返回为准**：工具数量、命名是否存在都取自本次响应，
> 再与代码里的基线 `EXPECTED_TOOLS` 比对 —— 数量对不上只报 `WARN`（提示更新基线），不会把服务端迭代误判成失败。

### 2.2 业务 Tool（只读，用于验证端到端链路）

| Tool | 在项目中的用途 |
|---|---|
| `now-time-info` | `mcd_mcp.py demo` 第 1 步；同时用于校准"北京时间"基准，避免因时区问题误判活动时间 |
| `campaign-calendar` | `mcd_mcp.py demo` 第 2 步；验证带参数/无参数两种只读调用的返回结构 |
| `available-coupons` | `mcd_mcp.py demo` 第 3 步；验证需要账号上下文的只读调用 |
| `list-nutrition-foods` | `mcd_mcp.py demo` 第 4 步；验证无参数只读调用 |

### 2.3 明确不调用的 Tool

本项目**不调用任何写操作**：`create-order`、`cancel-order`、`mall-create-order`、`party-order-create`、`auto-bind-coupons`、`draw-lottery`、`delivery-create-address`。

`doctor.py --probe-auth` 会额外发两个**故意失败**的请求（空 Token / 错误 Token）来钉死鉴权错误形态，两者都不会产生任何业务副作用。

## 3. 调用流程

```
读取环境变量 MCD_MCP_TOKEN
        |
        v
POST initialize  -----------------------> 记录 Mcp-Session-Id
        |                                （若响应为 SSE，则逐行解析 data:）
        v
POST notifications/initialized  ---------> 无响应（通知类）
        |
        v
POST tools/list  -----------------------> 35 个工具 + inputSchema
        |
        +--> 与基线做差集 / 命名核对
        |
        v
POST tools/call {name, arguments}  -----> 业务数据（只读）
```

### 关键实现细节

1. **响应两种形态都要处理**：可能是 `application/json`，也可能是 `text/event-stream`，需按 `data:` 逐行拼接。
2. **会话头**：`initialize` 响应带 `Mcp-Session-Id`，后续请求必须回传。
3. **鉴权失败的状态码与 body 都不是单一的**（2026-10-23 实测两轮一致），必须状态码 + body 一起判：

| 情况 | HTTP | Body |
|---|---|---|
| 未带 Token | **403** | 业务信封 `{"code":"0001","msg":"系统错误","data":null}` |
| Token 无效 | **401** | 纯文本 `当前鉴权码不存在或已失效!`（不是 JSON） |
| Token 正常 | 200 | 标准 JSON-RPC |

## 4. 业务价值

### 4.1 解决的问题

麦当劳 MCP 的官方文档与实际服务存在若干不一致，且**部分错误是静默的**：

| 问题 | 后果 |
|---|---|
| 文档列 33 个工具，实际 35 个 | 按文档做的规划会漏工具 |
| 派对工具名文档拼错 | 照抄调用直接失败（返 JSON-RPC error，不是 404） |
| 鉴权失败有 403/401 两种状态码，且 body 形态各不相同 | 只写 `if status == 401` 的客户端会漏掉"没带 Token"这一整类 |
| 算价字段名传错返回 0 元 | **不报错**，被误判为"商品不可售" |
| 金额单位是分 | 价格放大 100 倍 |

### 4.2 本项目的处理方式

把这些约束**从"读文档记住"变成"可执行的断言"**：

- 工具数量、命名、差集 → 每次运行都重新校验，服务端迭代后主动报警；
- 鉴权错误形态 → 用 `--probe-auth` 现场复现并打印，而不是相信文档；
- 陷阱字典（`PITFALLS.md`）→ 每条附"现象 / 原因 / 正确做法 / 复现方式"，可直接对照排查。

### 4.3 目标用户

- 正在接入麦当劳 MCP 的开发者（第一小时就少走弯路）；
- 需要把 MCP 接进自己的工具链、插件或自动化流程的团队；
- 想把 MCP 接入检查放进 CI 的项目（`--json` 输出可直接断言）。

### 4.4 关于 `mcp-config.example.json` 的字段差异

该示例用的是最常见的 `mcpServers` + `url` + `headers` 形状，但各客户端对 `type` 的叫法并不统一：

| 客户端类型 | `type` 取值 |
|---|---|
| 编辑器与 CLI 类（如 VS Code） | `http` |
| 插件类（如 Cline） | `streamableHttp` |
| 部分桌面客户端 | 不支持带 `headers` 的远程 HTTP Server |

该文件的用途是演示占位符写法（Token 只允许 `${MCD_MCP_TOKEN}` 这种形式），按你所用客户端的字段名调整即可。

---

## 5. 安全与合规

- `mcp-config.example.json` 只使用环境变量占位符；
- 项目只读优先，不代下单、不代扣积分；
- 所有结论均标注实测日期（2026-10-23），服务端变更后可自行复跑验证。
