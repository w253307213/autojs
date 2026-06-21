#!/usr/bin/env python3
"""
10:00 自适应网格 — 动态间距版
每天10:00触发，流程：
  1. 获取每个标的最近60天的日线数据
  2. 从日线数据中重新计算日波动率
  3. 基于最新波动率动态计算最优阈值（网格间距）
  4. 用动态阈值判断是否需要市值平衡调整
"""
import json, os, re, sys
import numpy as np
from scipy import stats
from datetime import datetime
from subprocess import run

MX_APIKEY = os.environ.get("MX_APIKEY", "mkt_k4G_Tse8OFGLi6WKBlOofot9VWIr3E4uG7FMtlf3QY0")
MX_DATA_DIR = os.path.expanduser("/root/.openclaw/workspace/skills/mx-data")

# 目标概率：每天触发概率 ~50%（即周触发2.5次）
TARGET_DAILY_PROB = 0.5
Z_SCORE = stats.norm.ppf(1 - TARGET_DAILY_PROB / 2)  # ≈ 0.6745

PORTFOLIO = {
    "003019": {"name": "宸展光电",       "target": 10000, "holdings": 300,  "min": 100, "sse": "SZ"},
    "513300": {"name": "纳斯达克100ETF", "target": 10000, "holdings": 3600, "min": 100, "sse": "SH"},
    "161005": {"name": "富国天惠LOF",    "target": 10000, "holdings": 3100, "min": 100, "sse": "SZ"},
    "159566": {"name": "新能源电池ETF",  "target": 10000, "holdings": 4300, "min": 100, "sse": "SZ"},
    "159851": {"name": "金融科技ETF",    "target": 10000, "holdings": 15600,"min": 100, "sse": "SZ"},
}

# ========== 数据获取 ==========

def fetch_ohlc_data(code):
    """获取近60天的日线OHLC数据
    查询格式：先用"近两个月每日开盘价_收盘价_最高价_最低价_成交量"获取完整数据
    兜底：用"日线60"获取（通常仅4天）
    返回 (closes, opens, highs, lows)
    """
    query_queries = [
        f"{code} 近两个月每日开盘价 收盘价 最高价 最低价 成交量",
        f"{code} 日线 60",
    ]

    out_dir = os.path.expanduser("/root/.openclaw/workspace/mx_data/output")

    for query in query_queries:
        try:
            env = os.environ.copy()
            env["MX_APIKEY"] = MX_APIKEY
            run(["python3", "mx_data.py", query],
                cwd=MX_DATA_DIR, capture_output=True, text=True, timeout=60, env=env)
        except:
            pass

        # 从JSON文件提取
        json_files = [f for f in os.listdir(out_dir)
                      if code in f and ("近两个月" in f or "日线" in f) and f.endswith("_raw.json")]
        json_files.sort(key=lambda x: os.path.getmtime(os.path.join(out_dir, x)), reverse=True)

        for jf in json_files[:2]:
            try:
                with open(os.path.join(out_dir, jf)) as f:
                    data = json.load(f)

                tables = data.get('data', {}).get('data', {}).get('searchDataResultDTO', {}).get('dataTableDTOList', [])

                for tbl in tables:
                    raw = tbl.get('rawTable', {})
                    closes_raw = raw.get('325898', [])
                    if not closes_raw or len(closes_raw) < 5:
                        continue

                    closes = []
                    opens = []
                    highs = []
                    lows = []
                    for v in closes_raw:
                        try:
                            closes.append(float(str(v).replace('元', '').strip()))
                        except:
                            pass

                    for v in raw.get('326269', []):
                        try:
                            opens.append(float(str(v).replace('元', '').strip()))
                        except:
                            pass

                    for v in raw.get('326339', []):
                        try:
                            highs.append(float(str(v).replace('元', '').strip()))
                        except:
                            pass

                    for v in raw.get('326386', []):
                        try:
                            lows.append(float(str(v).replace('元', '').strip()))
                        except:
                            pass

                    if len(closes) >= 5:
                        return closes, opens, highs, lows
            except:
                continue

    return None


# ========== 波动率计算 ==========

def calc_volatility(closes, opens, highs, lows):
    """从日线数据计算日波动率和日内振幅"""
    # 日收益率波动率
    rets = [(closes[i] - closes[i+1]) / closes[i+1] * 100 for i in range(len(closes)-1)]
    daily_vol = float(np.std(rets, ddof=1))

    # 日内振幅
    n = min(len(highs), len(lows), len(closes))
    if n >= 3:
        intra_ranges = [(highs[i] - lows[i]) / closes[i] * 100 for i in range(n)]
        avg_intra = float(np.mean(intra_ranges))
    else:
        avg_intra = float(np.mean([abs(c - o) / o * 100 for c, o in zip(closes, opens)]))

    return daily_vol, avg_intra


def calc_optimal_threshold(daily_vol, avg_intra):
    """
    基于最新波动率动态计算最优阈值
    - 目标：每天50%概率触发一次（周2.5次）
    - 公式：threshold = Z * daily_vol,  Z ≈ 0.6745
    - 下限保护：不低于日内振幅的40%（防止噪音触发）
    """
    threshold = round(Z_SCORE * daily_vol, 1)
    min_threshold = max(round(avg_intra * 0.4, 1), 0.5)
    if threshold < min_threshold:
        threshold = min_threshold

    # 预期触发率
    z_actual = threshold / daily_vol if daily_vol > 0 else 3
    p_daily = 2 * (1 - stats.norm.cdf(z_actual))
    p_weekly = p_daily * 5

    return threshold, p_daily, p_weekly


# ========== 市值平衡计算 ==========

def calc_adjustment(code, info, price, threshold):
    """用动态阈值计算是否需要调整"""
    val = info["holdings"] * price
    target = info["target"]
    dev_pct = (val - target) / target * 100
    upper = target * (1 + threshold / 100)
    lower = target * (1 - threshold / 100)

    result = {
        "code": code, "name": info["name"], "price": price,
        "holdings": info["holdings"], "value": round(val, 2),
        "target": target, "dev_pct": round(dev_pct, 2),
        "threshold": threshold, "upper": round(upper), "lower": round(lower),
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


# ========== 报告生成 ==========

def build_report(all_data):
    """生成完整报告"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append(f"{'='*64}")
    lines.append(f"  10:00 自适应网格报告（动态间距）")
    lines.append(f"  时间: {now}")
    lines.append(f"  备注: 阈值基于最新{all_data[0]['n_days']}天数据动态计算")
    lines.append(f"{'='*64}")

    total_buy = 0.0
    total_sell = 0.0
    triggers = 0

    for d in all_data:
        code = d["code"]
        lines.append(f"\n  {'─'*56}")
        lines.append(f"  {code} {d['name']:<12} 当前: {d['price']:.3f}元 | 日波动: {d['daily_vol']:.2f}%")

        if d["error"]:
            lines.append(f"  获取数据失败，跳过")
            continue

        # 动态阈值信息
        tag = "⚡ 需调整" if d["trigger"] else "✓ 持有"
        lines.append(f"  持仓: {d['holdings']:,}股 | 市值: {d['value']:,.0f}元 | 目标: {d['target']:,}元")
        lines.append(f"  偏离: {d['dev_pct']:+.2f}% | 动态阈值: ±{d['threshold']:.1f}% (日波动{d['daily_vol']:.2f}% × {Z_SCORE:.3f})")
        lines.append(f"  区间: {d['lower']:,} ~ {d['upper']:,}元 | {tag}")

        if d["trigger"]:
            triggers += 1
            dr = "买入" if d["dir"] == "BUY" else "卖出"
            lines.append(f"  ⚡ 操作: {dr} {d['shares']:,}股 @ {d['price']:.3f} = {d['amount']:,.0f}元")
            lines.append(f"     新持仓: {d['new_holdings']:,}股 (市值 {d['new_holdings']*d['price']:,.0f}元)")
            lines.append(f"     华宝委托: {dr} {code} {d['shares']}股")
            if d["dir"] == "SELL":
                total_sell += d["amount"]
            else:
                total_buy += d["amount"]
        else:
            lines.append(f"  操作: 无需调整")

    lines.append(f"\n  {'='*64}")
    lines.append(f"  今日汇总")
    lines.append(f"  触发调整: {triggers} / {len(all_data)} 个标的")
    if total_buy or total_sell:
        lines.append(f"  总买入: {total_buy:,.0f}元 | 总卖出: {total_sell:,.0f}元")
        net = total_sell - total_buy
        lines.append(f"  资金净流: {'+' if net >= 0 else ''}{net:+,.0f}元")
    total_val = sum(PORTFOLIO[d["code"]]["holdings"] * d["price"]
                    for d in all_data if not d["error"])
    lines.append(f"  组合市值: {total_val:,.0f}元 / 目标50,000元")
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


# ========== 主流程 ==========

if __name__ == "__main__":
    print()
    print(f"  {'='*56}")
    print(f"  10:00 自适应网格 — 动态间距版")
    print(f"  日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  方法: 获取60天日线 → 算波动率 → 动态阈值 → 平衡判断")
    print(f"  组合: 5个标的 × 1万元 = 5万元")
    print(f"  {'='*56}")

    all_data = []

    for code, info in PORTFOLIO.items():
        print(f"\n  {'─'*56}")
        print(f"  [{code} {info['name']}] 获取日线数据...")

        ohlc = fetch_ohlc_data(code)
        if ohlc is None:
            print(f"  ✗ 获取失败")
            all_data.append({
                "code": code, "name": info["name"], "error": True,
                "price": 0, "holdings": info["holdings"],
                "value": 0, "target": info["target"],
                "daily_vol": 0, "threshold": 0,
                "dev_pct": 0, "trigger": False,
            })
            continue

        closes, opens, highs, lows = ohlc
        latest_price = closes[0]
        n_days = len(closes)

        # 动态计算波动率
        daily_vol, avg_intra = calc_volatility(closes, opens, highs, lows)

        # 动态计算最优阈值
        threshold, p_daily, p_weekly = calc_optimal_threshold(daily_vol, avg_intra)

        print(f"  最新价: {latest_price:.3f} | 数据天数: {n_days}")
        print(f"  日波动率: {daily_vol:.2f}% | 日内振幅: {avg_intra:.2f}%")
        print(f"  动态阈值: ±{threshold:.1f}% (预期触发 {p_daily*100:.0f}%/天, {p_weekly:.1f}次/周)")

        # 用动态阈值做平衡判断
        r = calc_adjustment(code, info, latest_price, threshold)
        r["daily_vol"] = round(daily_vol, 2)
        r["avg_intra"] = round(avg_intra, 2)
        r["n_days"] = n_days
        r["error"] = False
        r["expected_daily_pct"] = round(p_daily * 100)
        r["expected_weekly"] = round(p_weekly, 1)
        all_data.append(r)

    report = build_report(all_data)
    print("\n" + report)
    save_report(report)