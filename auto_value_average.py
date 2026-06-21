#!/usr/bin/env python3
"""
每日价值平均网格 — 自动版（统一1万元基准）
调用妙想mx-data获取实时价格，自动计算调整指令
"""
import json
import os
import subprocess
import sys
from datetime import datetime

MX_APIKEY = os.environ.get("MX_APIKEY", "mkt_k4G_Tse8OFGLi6WKBlOofot9VWIr3E4uG7FMtlf3QY0")
MX_DATA_DIR = os.path.expanduser("/root/.openclaw/workspace/skills/mx-data")

# ==================== 配置区（统一1万元/标的） ====================

PORTFOLIO = {
    "003019": {
        "name": "宸展光电",
        "target_value": 10000,
        "threshold_pct": 2.9,
        "holdings": 300,
        "min_trade": 100,
        "sse": "SZ",
    },
    "513300": {
        "name": "纳斯达克100ETF",
        "target_value": 10000,
        "threshold_pct": 1.3,
        "holdings": 3600,
        "min_trade": 100,
        "sse": "SH",
    },
    "161005": {
        "name": "富国天惠LOF",
        "target_value": 10000,
        "threshold_pct": 0.7,
        "holdings": 3100,
        "min_trade": 100,
        "sse": "SZ",
    },
    "159566": {
        "name": "新能源电池ETF",
        "target_value": 10000,
        "threshold_pct": 1.5,
        "holdings": 4300,
        "min_trade": 100,
        "sse": "SZ",
    },
    "159851": {
        "name": "金融科技ETF",
        "target_value": 10000,
        "threshold_pct": 1.3,
        "holdings": 15600,
        "min_trade": 100,
        "sse": "SZ",
    },
}


def fetch_price(code):
    """通过妙想mx-data获取实时价格"""
    try:
        env = os.environ.copy()
        env["MX_APIKEY"] = MX_APIKEY
        result = subprocess.run(
            ["python3", "mx_data.py", f"{code} 最新行情"],
            cwd=MX_DATA_DIR,
            capture_output=True, text=True, timeout=30, env=env
        )
        output = result.stdout + result.stderr
        import re
        prices = re.findall(r'(?:最新价|收盘价)[^\d]*(\d+\.\d+)', output)
        if prices:
            return float(prices[0])
        return None
    except Exception as e:
        print(f"  获取{code}价格失败: {e}")
        return None


def get_current_prices():
    """获取所有标的最新价格"""
    prices = {}
    print("获取实时价格中...")
    for code in PORTFOLIO:
        p = fetch_price(code)
        if p:
            prices[code] = p
            print(f"  {code}: {p:.3f}")
        else:
            print(f"  {code}: 获取失败")
    return prices


def calculate(code, info, current_price):
    """计算单个标的的价值平均调整"""
    target = info["target_value"]
    threshold = info["threshold_pct"]
    holdings = info["holdings"]
    min_trade = info["min_trade"]

    current_value = holdings * current_price
    deviation_pct = (current_value - target) / target * 100
    deviation_amt = current_value - target

    upper = target * (1 + threshold / 100)
    lower = target * (1 - threshold / 100)

    result = {
        "code": code,
        "name": info["name"],
        "price": round(current_price, 3),
        "holdings": holdings,
        "current_value": round(current_value, 2),
        "target_value": target,
        "deviation_pct": round(deviation_pct, 2),
        "threshold_pct": threshold,
        "upper": round(upper, 2),
        "lower": round(lower, 2),
        "triggered": False,
        "action": "持有",
        "trade_shares": 0,
        "trade_direction": "",
        "trade_amount": 0,
        "new_holdings": holdings,
    }

    if current_value > upper:
        sell_target = current_value - target
        sell_shares = int(sell_target / current_price / min_trade) * min_trade
        if sell_shares >= min_trade:
            result["action"] = f"卖出 {sell_shares:,}股"
            result["trade_shares"] = sell_shares
            result["trade_direction"] = "SELL"
            result["trade_amount"] = round(sell_shares * current_price, 2)
            result["new_holdings"] = holdings - sell_shares
            result["triggered"] = True
    elif current_value < lower:
        buy_target = target - current_value
        buy_shares = int(buy_target / current_price / min_trade) * min_trade
        if buy_shares >= min_trade:
            result["action"] = f"买入 {buy_shares:,}股"
            result["trade_shares"] = buy_shares
            result["trade_direction"] = "BUY"
            result["trade_amount"] = round(buy_shares * current_price, 2)
            result["new_holdings"] = holdings + buy_shares
            result["triggered"] = True

    return result


def generate_report(results):
    """生成报告"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("=" * 72)
    lines.append(f"  每日价值平均网格报告（统一1万元基准）")
    lines.append(f"  生成时间: {today}")
    lines.append("=" * 72)

    total_triggered = 0
    total_buy = 0.0
    total_sell = 0.0

    for code, r in results.items():
        status = "需调整" if r["triggered"] else "持有"
        lines.append(f"\n{'─'*60}")
        lines.append(f" {code} {r['name']}  {status}")
        lines.append(f" 价格: {r['price']:.3f} | 持仓: {r['holdings']:,}股 | 市值: {r['current_value']:,.0f}元")
        lines.append(f" 目标: {r['target_value']:,}元 | 偏离: {r['deviation_pct']:+.2f}% (阈值±{r['threshold_pct']:.1f}%)")

        if r["triggered"]:
            total_triggered += 1
            d = "买入" if r["trade_direction"] == "BUY" else "卖出"
            lines.append(f" > 操作: {d} {r['trade_shares']:,}股 @ {r['price']:.3f} = {r['trade_amount']:,.0f}元")
            lines.append(f"   操作后: {r['new_holdings']:,}股")
            if r["trade_direction"] == "SELL":
                total_sell += r["trade_amount"]
            else:
                total_buy += r["trade_amount"]
        else:
            lines.append(f" 操作: 不操作")

    lines.append(f"\n{'='*60}")
    lines.append(f" 汇总: 触发 {total_triggered} 个 | 买入 {total_buy:,.0f}元 | 卖出 {total_sell:,.0f}元")
    lines.append(f"       净现金流: {total_sell - total_buy:+,.0f}元")
    lines.append(f"       组合目标: 50,000元 (5×1万)")
    lines.append(f"{'='*60}")

    return "\n".join(lines)


def log_report(report):
    """保存报告到文件"""
    today = datetime.now().strftime("%Y%m%d")
    log_dir = os.path.expanduser("/workspace/value_avg_logs")
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"daily_{today}.txt")
    with open(path, "w") as f:
        f.write(report)
    print(f"\n报告已保存: {path}")


if __name__ == "__main__":
    print("=" * 72)
    print("  每日价值平均网格 (自动版)")
    print(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 72)

    prices = get_current_prices()
    if not prices:
        print("  无法获取价格，请手动输入")
        prices = {}
        for code, info in PORTFOLIO.items():
            val = input(f"  {code} {info['name']} 价格: ").strip()
            if val:
                prices[code] = float(val)

    if not prices:
        print("  无价格数据，退出")
        sys.exit(1)

    results = {}
    for code, info in PORTFOLIO.items():
        if code in prices:
            results[code] = calculate(code, info, prices[code])

    report = generate_report(results)
    print("\n" + report)
    log_report(report)