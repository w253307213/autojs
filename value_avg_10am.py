#!/usr/bin/env python3
"""
10:00 市值平衡计算器
每天10:00触发，获取实时价格 → 计算价值平均调整 → 输出买卖指令
统一基准：每个标的持仓市值1万元，组合总目标5万元
"""
import json, os, re, sys
from datetime import datetime
from subprocess import run

MX_APIKEY = os.environ.get("MX_APIKEY", "mkt_k4G_Tse8OFGLi6WKBlOofot9VWIr3E4uG7FMtlf3QY0")
MX_DATA_DIR = os.path.expanduser("/root/.openclaw/workspace/skills/mx-data")

PORTFOLIO = {
    "003019": {"name": "宸展光电",       "target": 10000, "threshold": 2.9, "holdings": 300,  "min": 100, "sse": "SZ"},
    "513300": {"name": "纳斯达克100ETF", "target": 10000, "threshold": 1.3, "holdings": 3600, "min": 100, "sse": "SH"},
    "161005": {"name": "富国天惠LOF",    "target": 10000, "threshold": 0.7, "holdings": 3100, "min": 100, "sse": "SZ"},
    "159566": {"name": "新能源电池ETF",  "target": 10000, "threshold": 1.5, "holdings": 4300, "min": 100, "sse": "SZ"},
    "159851": {"name": "金融科技ETF",    "target": 10000, "threshold": 1.3, "holdings": 15600,"min": 100, "sse": "SZ"},
}

def fetch_latest_close(code):
    """从mx-data获取最新收盘价（优先解析stdout，其次读取JSON文件）"""
    try:
        env = os.environ.copy()
        env["MX_APIKEY"] = MX_APIKEY
        r = run(["python3", "mx_data.py", f"{code} 最新行情"],
                cwd=MX_DATA_DIR, capture_output=True, text=True, timeout=60, env=env)
        output = r.stdout + r.stderr

        # 从stdout直接解析价格（在表格行中找数值）
        # Pattern: 收盘价列中的数字
        prices_found = re.findall(r'(\d+\.\d+)(?:元)?', output)
        if prices_found:
            # 取最后一个表格中的价格（最新行情表的收盘价）
            nums = [float(x) for x in prices_found if 0.1 < float(x) < 1000]
            if nums:
                return nums[0]

        # 兜底：从最新生成的JSON文件读取
        out_dir = os.path.expanduser("/root/.openclaw/workspace/mx_data/output")
        json_files = [f for f in os.listdir(out_dir)
                      if code in f and "最新行情" in f and f.endswith("_raw.json")]
        json_files.sort(key=lambda x: os.path.getmtime(os.path.join(out_dir, x)), reverse=True)
        for jf in json_files[:1]:
            with open(os.path.join(out_dir, jf)) as f:
                data = json.load(f)
            tables = data.get('data',{}).get('data',{}).get('searchDataResultDTO',{}).get('dataTableDTOList',[])
            for tbl in tables:
                raw = tbl.get('rawTable', {})
                for key in ['325898', '最新价', '收盘价']:
                    vals = raw.get(key, [])
                    if vals:
                        return float(str(vals[0]).replace('元','').strip())
        return None
    except:
        return None


# 已知最新价格（自动获取失败时的兜底值）
FALLBACK_PRICES = {
    "003019": 32.95,
    "513300": 2.752,
    "161005": 3.184,
    "159566": 2.292,
    "159851": 0.638,
}

def get_prices():
    """获取所有标的价格（全自动，无交互）"""
    prices = {}
    print(f"\n  {'─'*56}")
    print(f"  正在获取各标的最新价格...")
    print(f"  {'─'*56}")

    for code, info in PORTFOLIO.items():
        p = fetch_latest_close(code)
        if p:
            print(f"  {code} {info['name']}: {p:.3f} 元 (实时)")
            prices[code] = p
        else:
            fb = FALLBACK_PRICES.get(code)
            print(f"  {code} {info['name']}: 使用参考价 {fb:.3f} 元 (非实时)")
            if fb:
                prices[code] = fb
    return prices


def calc(code, info, price):
    """计算单个标的是否需要市值平衡"""
    val = info["holdings"] * price
    target = info["target"]
    thr = info["threshold"]
    dev_pct = (val - target) / target * 100

    upper = target * (1 + thr / 100)
    lower = target * (1 - thr / 100)

    result = {
        "code": code, "name": info["name"], "price": price,
        "holdings": info["holdings"], "value": round(val, 2),
        "target": target, "dev_pct": round(dev_pct, 2),
        "threshold": thr, "upper": round(upper), "lower": round(lower),
        "trigger": False, "action": "持有", "shares": 0, "dir": "",
    }

    if val > upper:
        sell_shares = int((val - target) / price / info["min"]) * info["min"]
        if sell_shares >= info["min"]:
            result.update({"trigger": True, "action": f"卖出 {sell_shares:,}股",
                           "shares": sell_shares, "dir": "SELL",
                           "new_holdings": info["holdings"] - sell_shares,
                           "amount": round(sell_shares * price, 2)})
    elif val < lower:
        buy_shares = int((target - val) / price / info["min"]) * info["min"]
        if buy_shares >= info["min"]:
            result.update({"trigger": True, "action": f"买入 {buy_shares:,}股",
                           "shares": buy_shares, "dir": "BUY",
                           "new_holdings": info["holdings"] + buy_shares,
                           "amount": round(buy_shares * price, 2)})
    return result


def run(prices):
    """主计算流程"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"{'='*64}")
    lines.append(f"  10:00 市值平衡报告")
    lines.append(f"  时间: {now}")
    lines.append(f"  基准: 每个标的 10,000 元 | 组合总目标: 50,000 元")
    lines.append(f"{'='*64}")

    results = []
    total_buy = 0.0
    total_sell = 0.0
    triggers = 0

    for code, info in PORTFOLIO.items():
        if code not in prices:
            lines.append(f"\n  {code}: 无价格数据，跳过")
            continue
        r = calc(code, info, prices[code])
        results.append(r)

        tag = "⚡ 需调整" if r["trigger"] else "✓ 持有"
        lines.append(f"\n  {'─'*56}")
        lines.append(f"  {code} {r['name']:<12} {tag}")
        lines.append(f"  价格: {r['price']:.3f} | 持仓: {r['holdings']:,}股 | 市值: {r['value']:,.0f}元")
        lines.append(f"  目标: {r['target']:,}元 | 偏离: {r['dev_pct']:+.2f}%")
        lines.append(f"  阈值: ±{r['threshold']:.1f}% ({r['lower']:,}~{r['upper']:,}元)")

        if r["trigger"]:
            triggers += 1
            d = "买入" if r["dir"] == "BUY" else "卖出"
            lines.append(f"  ⚡ 操作: {d} {r['shares']:,}股 @ {r['price']:.3f} = {r['amount']:,.0f}元")
            lines.append(f"     操作后: {r['new_holdings']:,}股 (市值 {r['new_holdings']*r['price']:,.0f}元)")
            lines.append(f"     华宝委托: {d} {code} {r['shares']}股")
            if r["dir"] == "SELL":
                total_sell += r["amount"]
            else:
                total_buy += r["amount"]
        else:
            lines.append(f"  操作: 无需调整 (市值在目标区间内)")

    lines.append(f"\n  {'='*64}")
    lines.append(f"  今日汇总")
    lines.append(f"  触发调整: {triggers} / {len(PORTFOLIO)} 个标的")
    if total_buy or total_sell:
        lines.append(f"  总买入: {total_buy:,.0f}元 | 总卖出: {total_sell:,.0f}元")
        net = total_sell - total_buy
        lines.append(f"  资金净流: {'+' if net >= 0 else ''}{net:+,.0f}元")
    lines.append(f"  组合市值: {sum(prices.get(c,0)*info['holdings'] for c,info in PORTFOLIO.items()):,.0f}元 / 目标50,000元")
    lines.append(f"{'='*64}")

    return "\n".join(lines)


def save_report(report):
    """保存报告"""
    today = datetime.now().strftime("%Y%m%d")
    log_dir = "/workspace/value_avg_logs"
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"10am_{today}.txt")
    with open(path, "w") as f:
        f.write(report)
    print(f"\n  报告已保存: {path}")


if __name__ == "__main__":
    print()
    print(f"  {'='*56}")
    print(f"  10:00 市值平衡计算器")
    print(f"  日期: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"  时间: {datetime.now().strftime('%H:%M')}")
    print(f"  组合: 5个标的 × 1万元 = 5万元")
    print(f"  {'='*56}")

    prices = get_prices()
    if not prices:
        print("\n  没有价格数据，退出")
        sys.exit(1)

    report = run(prices)
    print("\n" + report)
    save_report(report)