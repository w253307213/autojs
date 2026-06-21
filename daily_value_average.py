#!/usr/bin/env python3
"""
每日价值平均网格 — 自动化计算脚本
每天17:00自动运行，生成次日交易指令
"""
import json
import os
import sys
from datetime import datetime

# ==================== 配置区 ====================

PORTFOLIO = {
    "003019": {
        "name": "宸展光电",
        "target_value": 10000,    # 目标市值
        "threshold_pct": 5.0,     # 触发阈值(%)
        "holdings": 300,          # 当前持仓股数
        "min_trade": 100,         # 最小交易单位(股)
        "sse": "SZ",              # 交易所
    },
    "513300": {
        "name": "纳斯达克100ETF",
        "target_value": 50000,
        "threshold_pct": 5.0,
        "holdings": 18100,
        "min_trade": 100,
        "sse": "SH",
    },
    "161005": {
        "name": "富国天惠LOF",
        "target_value": 30000,
        "threshold_pct": 3.0,
        "holdings": 9400,
        "min_trade": 100,
        "sse": "SZ",
    },
    "159566": {
        "name": "新能源电池ETF",
        "target_value": 50000,
        "threshold_pct": 3.0,
        "holdings": 21800,
        "min_trade": 100,
        "sse": "SZ",
    },
    "159851": {
        "name": "金融科技ETF",
        "target_value": 50000,
        "threshold_pct": 5.0,
        "holdings": 78400,
        "min_trade": 100,
        "sse": "SZ",
    },
}

# ==================== 计算逻辑 ====================

def calculate(code, info, current_price):
    """计算单个标的的价值平均调整"""
    name = info["name"]
    target = info["target_value"]
    threshold = info["threshold_pct"]
    holdings = info["holdings"]
    min_trade = info["min_trade"]
    sse = info["sse"]

    current_value = holdings * current_price
    deviation_pct = (current_value - target) / target * 100
    deviation_amt = current_value - target

    upper = target * (1 + threshold / 100)
    lower = target * (1 - threshold / 100)

    action = "持有"
    trade_shares = 0
    trade_direction = ""
    trade_amount = 0.0
    new_holdings = holdings
    triggered = False

    if current_value > upper:
        # 市值偏高 → 卖出
        sell_target = current_value - target
        sell_shares = int(sell_target / current_price / min_trade) * min_trade
        if sell_shares >= min_trade:
            action = f"卖出 {sell_shares:,}股"
            trade_shares = sell_shares
            trade_direction = "SELL"
            trade_amount = sell_shares * current_price
            new_holdings = holdings - sell_shares
            triggered = True
    elif current_value < lower:
        # 市值偏低 → 买入
        buy_target = target - current_value
        buy_shares = int(buy_target / current_price / min_trade) * min_trade
        if buy_shares >= min_trade:
            action = f"买入 {buy_shares:,}股"
            trade_shares = buy_shares
            trade_direction = "BUY"
            trade_amount = buy_shares * current_price
            new_holdings = holdings + buy_shares
            triggered = True

    return {
        "code": code,
        "name": name,
        "price": current_price,
        "holdings": holdings,
        "current_value": round(current_value, 2),
        "target_value": target,
        "deviation_pct": round(deviation_pct, 2),
        "deviation_amt": round(deviation_amt, 2),
        "threshold_pct": threshold,
        "upper": round(upper, 2),
        "lower": round(lower, 2),
        "triggered": triggered,
        "action": action,
        "trade_shares": trade_shares,
        "trade_direction": trade_direction,
        "trade_amount": round(trade_amount, 2),
        "new_holdings": new_holdings,
        "sse": sse,
        "min_trade": min_trade,
    }


def run(current_prices):
    """传入当前价格字典，运行所有标的价值平均计算"""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("=" * 72)
    lines.append(f"📊 每日价值平均网格报告")
    lines.append(f"   生成时间: {today}")
    lines.append("=" * 72)

    total_triggered = 0
    total_sell = 0.0
    total_buy = 0.0

    for code, info in PORTFOLIO.items():
        price = current_prices.get(code)
        if price is None:
            lines.append(f"\n⚠️ {code} {info['name']}：缺少价格数据，跳过")
            continue

        result = calculate(code, info, price)
        status = "🔄 需调整" if result["triggered"] else "✅ 持有"
        lines.append(f"\n{'─' * 72}")
        lines.append(f" {code} {result['name']}  {status}")
        lines.append(f" {'─' * 72}")
        lines.append(f" 当前价:    {result['price']:.3f} 元")
        lines.append(f" 持仓:      {result['holdings']:,} 股")
        lines.append(f" 当前市值:  {result['current_value']:,.0f} 元")
        lines.append(f" 目标市值:  {result['target_value']:,} 元")
        lines.append(f" 偏离:      {result['deviation_pct']:+.2f}% ({result['deviation_amt']:+,.0f}元)")
        lines.append(f" 阈值:      ±{result['threshold_pct']:.0f}% (上限{result['upper']:,.0f} / 下限{result['lower']:,.0f})")

        if result["triggered"]:
            total_triggered += 1
            direction_cn = "买入" if result["trade_direction"] == "BUY" else "卖出"
            lines.append(f" ⚡ 操作建议: {direction_cn} {result['trade_shares']:,}股 @ {result['price']:.3f}")
            lines.append(f"    金额:    {result['trade_amount']:,.0f} 元")
            lines.append(f"    操作后:  {result['new_holdings']:,} 股 (市值 {result['new_holdings']*result['price']:,.0f}元)")
            lines.append(f"    华宝条件单: {direction_cn} {code} {result['trade_shares']}股 价格{result['price']:.3f}")
            if result["trade_direction"] == "SELL":
                total_sell += result["trade_amount"]
            else:
                total_buy += result["trade_amount"]
        else:
            lines.append(f" 操作:      {'不操作 (在阈值内)'}")

    lines.append(f"\n{'=' * 72}")
    lines.append(f"📋 今日汇总")
    lines.append(f"  触发调整: {total_triggered} 个标的")
    if total_buy > 0:
        lines.append(f"  总买入:   {total_buy:,.0f} 元")
    if total_sell > 0:
        lines.append(f"  总卖出:   {total_sell:,.0f} 元")
    lines.append(f"  资金净流: {'+' if total_sell > total_buy else ''}{total_sell - total_buy:+,.0f} 元")
    lines.append(f"{'=' * 72}")

    return "\n".join(lines), total_triggered


# ==================== 主入口 ====================

if __name__ == "__main__":
    print("=" * 72)
    print("🔄 每日价值平均网格计算器")
    print("用法: python3 daily_value_average.py")
    print("=" * 72)
    print()
    print("请手动输入各标的当前价格 (留空则跳过):")
    print()

    current_prices = {}
    for code, info in PORTFOLIO.items():
        val = input(f"  {code} {info['name']} 当前价 [{info.get('last_price','?')}] : ").strip()
        if val:
            try:
                current_prices[code] = float(val)
            except:
                print(f"    跳过 {code}")

    if not current_prices:
        print("\n⚠️ 未输入任何价格，无法计算")
        sys.exit(1)

    report, triggered = run(current_prices)
    print("\n" + report)