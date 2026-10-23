#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcd-mcp-doctor —— 麦当劳中国 MCP Server 接入体检

零依赖（仅标准库 + 同目录的 mcd_mcp.py），只做只读检查，不会下单、不会扣积分。

用法：
    set MCD_MCP_TOKEN=你的token
    python doctor.py                 # 体检
    python doctor.py --probe-auth    # 额外探测「无 Token / 错 Token」的真实错误形态
    python doctor.py --json          # 机器可读输出

退出码：0 = 全部通过（可能有 WARN）；2 = 存在问题（有 FAIL）。
"""
import argparse
import json
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# 2026-10-23 实测基线；服务端迭代后若数量变化请更新这里
EXPECTED_TOOLS = [
    "auto-bind-coupons", "available-coupons", "calculate-price", "campaign-calendar",
    "cancel-order", "create-order", "delivery-create-address", "delivery-query-addresses",
    "delivery-query-stores", "draw-lottery", "list-nutrition-foods", "mall-create-order",
    "mall-order-detail", "mall-order-list", "mall-points-products", "mall-product-detail",
    "now-time-info", "order-list", "party-order-create", "query-lottery-info",
    "query-meal-assistance", "query-meal-detail", "query-meals", "query-my-account",
    "query-my-coupons", "query-my-prizes", "query-nearby-stores", "query-order",
    "query-party-city", "query-party-store", "query-party-store-date",
    "query-party-store-session", "query-promotions", "query-store-coupons",
    "query-survey-coupon",
]

# 官方 README §3 写的名字（实际不存在），用来提醒后来者
DOC_ONLY_NAMES = ["query-partystore-date", "query-partystore-session"]

WRITE_TOOLS = {
    "create-order", "cancel-order", "mall-create-order", "party-order-create",
    "auto-bind-coupons", "draw-lottery", "delivery-create-address",
}

results = []


def add(level, item, detail):
    results.append({"level": level, "item": item, "detail": detail})


def probe_auth(mcd_mcp):
    """官方文档说鉴权失败返 401，实测是 HTTP 200 + 业务码 / 纯文本。这里把它复现出来。"""
    saved_tok = mcd_mcp.TOKEN
    saved_sid = mcd_mcp._session_id
    payload = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
               "params": {"protocolVersion": mcd_mcp.PROTO, "capabilities": {},
                          "clientInfo": {"name": "doctor", "version": "1.0"}}}
    try:
        # 复现真正的「未带 Token」形态：连会话头也要清掉，否则不是干净的无凭据请求
        mcd_mcp.TOKEN = ""
        mcd_mcp._session_id = None
        _h, body = mcd_mcp._post(payload)
        code = None
        try:
            code = json.loads(body).get("code")
        except Exception:  # noqa: BLE001
            pass
        add("INFO", "无 Token 时",
            "HTTP %s | 业务 code=%s | body 前缀=%r"
            % (mcd_mcp.LAST_STATUS, code, body.strip()[:40]))

        mcd_mcp.TOKEN = "invalid_token_for_doctor_probe"
        mcd_mcp._session_id = None
        _h2, body2 = mcd_mcp._post(payload)
        add("INFO", "错 Token 时",
            "HTTP %s | body=%r（不是 JSON，别只判 401）"
            % (mcd_mcp.LAST_STATUS, body2.strip()[:60]))
    except Exception as e:  # noqa: BLE001
        add("WARN", "--probe-auth", "探测过程出错：%s: %s" % (type(e).__name__, e))
    finally:
        mcd_mcp.TOKEN = saved_tok
        mcd_mcp._session_id = saved_sid


def run_checks(args):
    try:
        import mcd_mcp
    except Exception as e:  # noqa: BLE001
        add("FAIL", "导入客户端",
            "无法 import mcd_mcp：%s（请确保 mcd_mcp.py 与 doctor.py 同目录）" % e)
        return

    # ---- 1. Token
    if not mcd_mcp.TOKEN:
        add("FAIL", "MCD_MCP_TOKEN", "环境变量为空，无法继续体检。设置后再跑：")
        add("INFO", "怎么设置（Windows）", "set MCD_MCP_TOKEN=你的token")
        add("INFO", "怎么设置（PowerShell）", '$env:MCD_MCP_TOKEN="你的token"')
        add("INFO", "怎么设置（macOS/Linux）", "export MCD_MCP_TOKEN=你的token")
        add("INFO", "去哪拿 Token", "https://open.mcd.cn/mcp 手机号登录 -> 控制台 -> 激活")
        if args.probe_auth:
            probe_auth(mcd_mcp)
        return
    add("PASS", "MCD_MCP_TOKEN", "已设置（长度 %d）" % len(mcd_mcp.TOKEN))

    # ---- 2. 鉴权形态探测（刻意前置：Token 无效/握手失败时最需要它，不能被提前 return 跳过）
    if args.probe_auth:
        probe_auth(mcd_mcp)

    # ---- 3. initialize
    if not mcd_mcp.handshake(verbose=False):
        add("FAIL", "initialize",
            "握手失败。最近一次错误：%s（常见原因：Token 失效 / 网络 / 协议不兼容）"
            % (mcd_mcp.LAST_ERROR or "响应不是 MCP 协议"))
        return
    si = mcd_mcp.SERVER_INFO or {}
    add("PASS", "initialize",
        "已连通 | 服务 %s %s | 协商协议 %s"
        % (si.get("name", "?"), si.get("version", ""),
           mcd_mcp.NEGOTIATED_PROTO or "(未返回)"))

    # ---- 4. tools/list
    ok, msgs = mcd_mcp.rpc("tools/list", {})
    names = []
    if ok:
        for m in msgs:
            if isinstance(m, dict) and isinstance(m.get("result"), dict):
                for t in (m["result"].get("tools") or []):
                    if isinstance(t, dict) and t.get("name"):
                        names.append(t["name"])
    if not names:
        add("FAIL", "tools/list", "拿不到工具列表（最近一次错误：%s）" % (mcd_mcp.LAST_ERROR or "-"))
        return

    add("PASS", "tools/list", "返回 %d 个工具（基线 %d）" % (len(names), len(EXPECTED_TOOLS)))
    if len(names) != len(EXPECTED_TOOLS):
        add("WARN", "工具数量",
            "与基线不一致，服务端可能已迭代，请更新 doctor.py 里的 EXPECTED_TOOLS")

    # ---- 5. 命名核对（文档 vs 实测）
    for dn in DOC_ONLY_NAMES:
        if dn in names:
            add("WARN", "文档命名", "%s 居然存在了，文档可能已修正" % dn)
        else:
            add("PASS", "文档命名",
                "%s 不存在（官方 README 写错，正确名是 query-party-store-*）" % dn)
    for real in ("query-party-store-date", "query-party-store-session"):
        add("PASS" if real in names else "FAIL", "真实命名", real)

    # ---- 6. 与基线做差集
    missing = [n for n in EXPECTED_TOOLS if n not in names]
    extra = [n for n in names if n not in EXPECTED_TOOLS]
    if missing:
        add("WARN", "基线缺失", "比基线少：%s" % ", ".join(missing))
    if extra:
        add("WARN", "基线新增", "比基线多：%s（文档没写，实测存在）" % ", ".join(extra))

    # ---- 7. 写操作提示
    present_write = sorted(WRITE_TOOLS & set(names))
    add("INFO", "写操作",
        "当前可用的 %d 个写操作：%s" % (len(present_write), ", ".join(present_write)))


def _disp_width(s):
    """终端显示宽度：中日韩全角算 2（纯码点补空格对不齐）。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in s)


def report(args):
    bad = [r for r in results if r["level"] == "FAIL"]
    if args.json:
        print(json.dumps({"ok": not bad, "results": results}, ensure_ascii=False, indent=2))
        return 0 if not bad else 2

    icon = {"PASS": "[ OK ]", "WARN": "[WARN]", "FAIL": "[FAIL]", "INFO": "[INFO]"}
    print("\n=== 麦当劳 MCP 接入体检 ===\n")
    w = max([_disp_width(r["item"]) for r in results] + [0]) + 2
    for r in results:
        pad = " " * max(1, w - _disp_width(r["item"]))
        print("%s %s%s%s" % (icon[r["level"]], r["item"], pad, r["detail"]))
    print("\n结论：%s（%d 项通过 / %d 项警告 / %d 项失败）" % (
        "可以正常使用" if not bad else "存在问题",
        sum(1 for r in results if r["level"] == "PASS"),
        sum(1 for r in results if r["level"] == "WARN"),
        len(bad)))
    return 0 if not bad else 2


def main():
    ap = argparse.ArgumentParser(description="麦当劳 MCP 接入体检")
    ap.add_argument("--probe-auth", action="store_true",
                    help="额外发 2 个请求探测鉴权错误形态（只读，无副作用）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args()

    try:
        run_checks(args)
    except Exception as e:  # noqa: BLE001
        # 兜底：任何未预期异常都不能吞掉已经收集到的体检结果
        add("FAIL", "运行异常", "%s: %s" % (type(e).__name__, e))

    return report(args)


if __name__ == "__main__":
    sys.exit(main())
