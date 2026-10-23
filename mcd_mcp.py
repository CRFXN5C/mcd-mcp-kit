#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦当劳中国 MCP 客户端（零依赖，仅标准库）

用法:
    set MCD_MCP_TOKEN=你的token          # Windows cmd
    $env:MCD_MCP_TOKEN="你的token"       # PowerShell
    export MCD_MCP_TOKEN=你的token       # macOS / Linux

    python mcd_mcp.py tools              # 列出全部工具
    python mcd_mcp.py call now-time-info # 调用单个工具
    python mcd_mcp.py call now-time-info --json-only   # 只看原始 JSON，跳过字段说明
    python mcd_mcp.py demo               # 跑一遍只读演示
    python mcd_mcp.py raw                # 排错：打印握手原始 HTTP 头与响应

退出码: 0 正常 / 1 用法错 / 2 鉴权或协议失败
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

# 管道/重定向下 Windows 默认用 GBK，碰到 GBK 覆盖不到的字符会 UnicodeEncodeError
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ENDPOINT = (os.environ.get("MCD_MCP_URL") or "https://mcp.mcd.cn").strip().rstrip("/")
TOKEN = os.environ.get("MCD_MCP_TOKEN", "").strip()
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
PROTO = "2025-06-18"

# Token 绝不能以明文 Bearer 发到 http:// 主机上；确需本地调试时显式放行
if not ENDPOINT.lower().startswith("https://"):
    if os.environ.get("MCD_MCP_ALLOW_INSECURE") != "1" or TOKEN:
        print("!! 端点必须是 https://（当前 %s）。\n"
              "   如需对本地调试端点发送摘要，请同时设置 MCD_MCP_ALLOW_INSECURE=1 且不设 Token。"
              % ENDPOINT, file=sys.stderr)
        sys.exit(2)

_session_id = None
_next_id = 0
LAST_STATUS = None      # 最近一次响应的 HTTP 状态码（失败时可能是异常信息字符串）
LAST_ERROR = None       # 最近一次失败原因（None 表示没失败）
NEGOTIATED_PROTO = None  # 服务端在 initialize 里协商出的协议版本
SERVER_INFO = {}        # 服务端 serverInfo


def _id():
    global _next_id
    _next_id += 1
    return _next_id


def _post(payload):
    """发一个 JSON-RPC 请求。

    任何网络层异常都在这里收敛成 (原因, 空响应)，绝不让 traceback 逃出去——
    否则调用方拿不到已经收集到的诊断信息。
    """
    global _session_id, LAST_STATUS, LAST_ERROR
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Accept-Encoding": "identity",
        "User-Agent": UA,
    }
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    if _session_id:
        headers["Mcp-Session-Id"] = _session_id

    req = urllib.request.Request(ENDPOINT, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            LAST_STATUS = r.status
            LAST_ERROR = None
            return dict(r.headers), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        LAST_STATUS = e.code
        LAST_ERROR = "HTTP %s" % e.code
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            body = ""
        return dict(e.headers), body
    except Exception as e:  # noqa: BLE001  URLError/Timeout/IncompleteRead/ValueError...
        LAST_STATUS = None
        LAST_ERROR = "%s: %s" % (type(e).__name__, e)
        return {}, ""


def _is_sse(headers, text):
    ctype = (headers.get("Content-Type") or headers.get("content-type") or "").lower()
    t = text.lstrip()
    return "text/event-stream" in ctype or t.startswith("event:") or t.startswith("data:")


def _parse(headers, text):
    """按 MCP 实际返回的两种形态解析：普通 JSON，或 SSE（一个事件可由多行 data: 拼成）。"""
    if _is_sse(headers, text):
        msgs = []
        buf = []
        for line in text.splitlines() + [""]:
            if not line.strip():
                if buf:
                    chunk = "\n".join(buf)
                    buf = []
                    if chunk and chunk.strip() != "[DONE]":
                        try:
                            msgs.append(json.loads(chunk))
                        except json.JSONDecodeError:
                            pass
                continue
            if line.startswith("data:"):
                # 规范：冒号后仅去掉一个前导空格
                seg = line[5:]
                buf.append(seg[1:] if seg.startswith(" ") else seg)
            # 其它字段（event:/id:/retry:/注释行）对解析 payload 无影响
        return msgs
    try:
        return [json.loads(text)]
    except json.JSONDecodeError:
        return []


def _diagnose(headers, text, msgs):
    """识别业务错误信封与纯文本错误。返回 (是否致命, 说明)。

    注意：不能只看「有没有 code 字段」——成功信封同样带 code=200。
    """
    stripped = text.strip()
    if len(msgs) == 1 and isinstance(msgs[0], dict) and "jsonrpc" not in msgs[0] and "code" in msgs[0]:
        m = msgs[0]
        code = str(m.get("code"))
        if code != "200":
            hint = ""
            if code == "0001":
                hint = "（多半是没带 Token 或 Token 为空）"
            return True, "服务返回业务错误: code=%s msg=%s%s" % (code, m.get("msg"), hint)
        return True, ("服务返回了非 JSON-RPC 响应（code=200 但缺 jsonrpc 字段）: %s"
                      % stripped[:200])
    if not msgs and stripped and not _is_sse(headers, text):
        return True, ("服务返回非 JSON 响应: %s（Token 失效/无效时会这样）"
                      % stripped[:300])
    if not msgs and LAST_ERROR:
        return True, "请求失败: %s" % LAST_ERROR
    return False, ""


def rpc(method, params=None, notify=False):
    """返回 (ok, msgs)。"""
    global _session_id
    payload = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        payload["params"] = params
    if not notify:
        payload["id"] = _id()

    headers, text = _post(payload)
    sid = headers.get("Mcp-Session-Id") or headers.get("mcp-session-id")
    if sid:
        _session_id = sid

    if not text.strip():
        return (True, []) if notify else (False, [])

    msgs = _parse(headers, text)
    fatal, why = _diagnose(headers, text, msgs)
    if fatal:
        print("!! " + why, file=sys.stderr)
        return False, []
    return True, msgs


def handshake(verbose=True):
    global NEGOTIATED_PROTO
    if not TOKEN:
        print("!! 环境变量 MCD_MCP_TOKEN 为空。先去 https://open.mcd.cn/mcp 申请 Token。",
              file=sys.stderr)
        return False

    ok, msgs = rpc("initialize", {
        "protocolVersion": PROTO,
        "capabilities": {"roots": {"listChanged": False}},
        "clientInfo": {"name": "mcd-cli", "version": "1.0.0"},
    })
    if not ok:
        return False

    got = False
    for m in msgs:
        if not isinstance(m, dict):
            continue
        if "error" in m:
            print("!! initialize 被拒: " + json.dumps(m["error"], ensure_ascii=False),
                  file=sys.stderr)
            return False
        res = m.get("result") or {}
        if isinstance(res, dict) and res:
            got = True
            NEGOTIATED_PROTO = res.get("protocolVersion") or PROTO
            si = res.get("serverInfo") or {}
            if isinstance(si, dict):
                SERVER_INFO.clear()
                SERVER_INFO.update(si)
            if verbose:
                print("服务: %s %s" % (si.get("name", "?"), si.get("version", "")))
                caps = ",".join((res.get("capabilities") or {}).keys()) or "-"
                print("协议: %s | 能力: %s" % (NEGOTIATED_PROTO, caps))
    if not got:
        print("!! initialize 没有拿到 result，响应可能不是 MCP 协议。用 `raw` 子命令看原文。",
              file=sys.stderr)
        return False

    rpc("notifications/initialized", notify=True)
    if verbose and _session_id:
        print("Session: %s" % _session_id)
    return True


def list_tools():
    ok, msgs = rpc("tools/list", {})
    if not ok:
        return []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        if "error" in m:
            print("!! tools/list 失败: " + json.dumps(m["error"], ensure_ascii=False),
                  file=sys.stderr)
            return []
        res = m.get("result")
        if not isinstance(res, dict):
            continue
        tools = res.get("tools") or []
        print("\n共 %d 个工具\n%s" % (len(tools), "-" * 78))
        for t in tools:
            if not isinstance(t, dict):
                continue
            name = t.get("name") or "?"
            print("%-30s %s" % (name, t.get("title") or ""))
            d = (t.get("description") or "").replace("\n", " ").strip()
            if d:
                print("%-30s %s" % ("", d[:110]))
        return tools
    return []


_MARKER = re.compile(r"^[ \t]*##[ \t]*Original Response[ \t]*$", re.M)


def call_tool(name, args=None, json_only=False):
    """json_only=True 时只打印服务端返回的 Original Response 原始 JSON，
    跳过前面的字段说明（服务端会把「结构说明 + 原始响应」拼在一段文本里）。"""
    ok, msgs = rpc("tools/call", {"name": name, "arguments": args or {}})
    if not ok:
        return None
    for m in msgs:
        if not isinstance(m, dict):
            continue
        if "error" in m:
            print("!! 调用失败: " + json.dumps(m["error"], ensure_ascii=False), file=sys.stderr)
            return None
        res = m.get("result")
        if not isinstance(res, dict) or not res:
            continue
        for c in res.get("content") or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text":
                text = c.get("text") or ""
                if json_only:
                    hit = _MARKER.search(text)
                    tail = text[hit.end():].strip() if hit else ""
                    if hit and tail:
                        try:
                            json.loads(tail)
                            text = tail
                        except json.JSONDecodeError:
                            print("!! --json-only: 标记之后的片段不是合法 JSON，输出完整文本",
                                  file=sys.stderr)
                    else:
                        print("!! --json-only: 未找到 '## Original Response' 标记，输出完整文本",
                              file=sys.stderr)
                print(text)
            else:
                print(json.dumps(c, ensure_ascii=False)[:600])
        if res.get("isError"):
            print("!! 工具返回 isError=true", file=sys.stderr)
        return res
    return None


def _parse_args(argv):
    """取 --args 的 JSON 值；越界/非法/非对象一律返回 (None, 错误说明)。"""
    if "--args" not in argv:
        return {}, None
    i = argv.index("--args")
    if i + 1 >= len(argv):
        return None, "--args 后面缺少 JSON 值"
    raw = argv[i + 1]
    try:
        val = json.loads(raw)
    except json.JSONDecodeError as e:
        return None, "--args 不是合法 JSON: %s" % e
    if not isinstance(val, dict):
        return None, "--args 必须是 JSON 对象（形如 {\"storeCode\":\"123\"}），收到 %s" % type(val).__name__
    return val, None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1].lower()

    if cmd == "raw":
        headers, text = _post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {"protocolVersion": PROTO, "capabilities": {},
                                          "clientInfo": {"name": "raw", "version": "0"}}})
        print("HTTP status:", LAST_STATUS, "| error:", LAST_ERROR)
        print("HTTP 响应头:")
        for k, v in headers.items():
            print("  %s: %s" % (k, v))
        print("\nbody:\n" + (text[:2000] or "(空)"))
        return 0

    # 先校验参数，再连服务器：参数错了不该白握手一次
    if cmd not in ("tools", "call", "demo"):
        print("未知子命令：%s\n" % cmd, file=sys.stderr)
        print(__doc__)
        return 1
    if cmd == "call" and len(sys.argv) < 3:
        print("用法: python mcd_mcp.py call <tool-name> [--args JSON] [--json-only]",
              file=sys.stderr)
        return 1

    json_only = "--json-only" in sys.argv[2:]
    args = {}
    if cmd == "call":
        args, err = _parse_args(sys.argv[2:])
        if err:
            print("!! " + err, file=sys.stderr)
            return 1

    if not handshake():
        return 2

    if cmd == "tools":
        list_tools()
    elif cmd == "call":
        call_tool(sys.argv[2], args, json_only=json_only)
    elif cmd == "demo":
        print("\n=== 1. now-time-info（当前时间）===")
        call_tool("now-time-info", json_only=json_only)
        print("\n=== 2. campaign-calendar（当月活动日历）===")
        call_tool("campaign-calendar", json_only=json_only)
        print("\n=== 3. available-coupons（当前可领券）===")
        call_tool("available-coupons", json_only=json_only)
        print("\n=== 4. list-nutrition-foods（营养数据）===")
        call_tool("list-nutrition-foods", json_only=json_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
