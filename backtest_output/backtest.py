#!/usr/bin/env python3
"""
40天历史回测：价值平均网格策略 — 参数优化
对每个标的，遍历不同阈值(0.3%~5.0%)，模拟40天策略表现
"""
import json, os, sys, math
import numpy as np
from scipy import stats
from datetime import datetime

out_dir = "/root/.openclaw/workspace/mx_data/output"

NAMES = {
    "003019": "宸展光电", "513300": "纳斯达克100ETF",
    "161005": "富国天惠LOF", "159566": "新能源电池ETF",
    "159851": "金融科技ETF",
}

FILES = {
    "003019": os.path.join(out_dir, "mx_data_003019_近两个月每日开盘价_收盘价_最高价_最低价_成交量_raw.json"),
    "513300": os.path.join(out_dir, "mx_data_513300_近两个月每日开盘价_收盘价_最高价_最低价_成交量_raw.json"),
    "161005": os.path.join(out_dir, "mx_data_161005_近两个月每日开盘价_收盘价_最高价_最低价_成交量_raw.json"),
    "159566": os.path.join(out_dir, "mx_data_159566_近两个月每日开盘价_收盘价_最高价_最低价_成交量_raw.json"),
    "159851": os.path.join(out_dir, "mx_data_159851_近两个月每日开盘价_收盘价_最高价_最低价_成交量_raw.json"),
}

TARGET_VALUE = 10000  # 每个标的1万元
MIN_TRADE = 100       # 最小交易单位
THRESHOLD_RANGE = [round(x * 0.1, 1) for x in range(3, 51)]  # 0.3% ~ 5.0% 步长0.1%
HOLD_REF_PCT = 0.5    # 初始持仓 = 目标市值/首日价 的50%

def load_data(code):
    """加载40天日线数据，返回 (dates[], opens[], closes[], highs[], lows[]) 从旧到新"""
    fpath = FILES[code]
    if not os.path.exists(fpath):
        return None
    with open(fpath) as f:
        data = json.load(f)

    tables = data.get('data',{}).get('data',{}).get('searchDataResultDTO',{}).get('dataTableDTOList',[])
    for tbl in tables:
        raw = tbl.get('rawTable', {})
        closes_raw = raw.get('325898', [])
        if len(closes_raw) < 10:
            continue
        dates = [str(h) for h in raw.get('headName', [])]
        opens = [float(str(v).replace('元','').strip()) for v in raw.get('326269', [])]
        closes = [float(str(v).replace('元','').strip()) for v in closes_raw]
        highs = [float(str(v).replace('元','').strip()) for v in raw.get('326339', [])]
        lows = [float(str(v).replace('元','').strip()) for v in raw.get('326386', [])]
        # 数据是新→旧，反转成旧→新
        dates.reverse()
        opens.reverse()
        closes.reverse()
        highs.reverse()
        lows.reverse()
        return dates, opens, closes, highs, lows
    return None


def simulate(code, threshold_pct, prices):
    """
    用给定阈值回测
    初始化：持仓 = 目标市值 / 首日价（取整到100股）
    每日检查市值，偏离超过阈值则调整到目标市值
    返回：(总交易次数, 最终收益率%, 最终市值偏差%)
    """
    target = TARGET_VALUE
    min_trade = MIN_TRADE

    # 初始持仓
    initial_price = prices[0]
    initial_shares = int(target / initial_price / min_trade) * min_trade

    holdings = initial_shares
    cash = 0  # 正=卖出入账, 负=买入支出
    trades = 0
    trade_log = []

    for i, price in enumerate(prices):
        current_value = holdings * price
        upper = target * (1 + threshold_pct / 100)
        lower = target * (1 - threshold_pct / 100)

        if current_value > upper:
            # 卖出
            sell_target = current_value - target
            sell_shares = int(sell_target / price / min_trade) * min_trade
            if sell_shares >= min_trade:
                holdings -= sell_shares
                cash += sell_shares * price
                trades += 1
                trade_log.append({'day': i, 'type': 'SELL', 'shares': sell_shares, 'price': price, 'balance': holdings * price})

        elif current_value < lower:
            # 买入
            buy_target = target - current_value
            buy_shares = int(buy_target / price / min_trade) * min_trade
            if buy_shares >= min_trade:
                fbuy = min(buy_shares, holdings * 3)  # 最多买到当前持仓3倍
                buy_shares = int(fbuy / min_trade) * min_trade
                if buy_shares >= min_trade:
                    holdings += buy_shares
                    cash -= buy_shares * price
                    trades += 1
                    trade_log.append({'day': i, 'type': 'BUY', 'shares': buy_shares, 'price': price, 'balance': holdings * price})

    # 最终表现
    final_price = prices[-1]
    final_value = holdings * final_price
    total_return = (final_value + cash - target) / target * 100
    deviation = (final_value - target) / target * 100

    # 计算胜率（卖出盈利比例）
    win_trades = 0
    total_sell_trades = 0
    sell_prices_bought = []
    for t in trade_log:
        if t['type'] == 'SELL':
            total_sell_trades += 1
    # 简化胜率：最后如果final_value接近target则好
    win_rate = max(0, 1 - abs(deviation) / threshold_pct) if threshold_pct > 0 else 0

    return trades, round(total_return, 2), round(deviation, 2), round(win_rate * 100, 1)


def run_backtest(code):
    """对单个标的运行完整回测"""
    data = load_data(code)
    if data is None:
        return None
    dates, opens, closes, highs, lows = data
    name = NAMES.get(code, code)

    # 实际波动率和日内振幅
    rets = [(closes[i] - closes[i-1]) / closes[i-1] * 100 for i in range(1, len(closes))]
    daily_vol = float(np.std(rets, ddof=1))
    intra_ranges = [(highs[i] - lows[i]) / closes[i] * 100 for i in range(len(closes))]
    avg_intra = float(np.mean(intra_ranges))

    # 遍历所有阈值
    results = []
    for thr in THRESHOLD_RANGE:
        trades, ret, dev, wr = simulate(code, thr, closes)
        results.append((thr, trades, ret, dev, wr))

    # 找最优
    # 评分标准：trade_count在8~20之间（40天约2-3次/周）且收益最高
    scored = []
    for thr, trades, ret, dev, wr in results:
        score = 0
        if trades >= 6 and trades <= 24:
            score += 30  # 交易频率达标
        score += max(0, ret) * 3  # 正收益加分
        score += wr * 0.5  # 胜率加分
        score -= abs(dev) * 2  # 最终偏差扣分
        scored.append((thr, trades, ret, dev, wr, round(score, 1)))

    # 按分数排序取前5
    scored.sort(key=lambda x: x[5], reverse=True)

    return {
        'code': code, 'name': name, 'n_days': len(closes),
        'latest_price': closes[-1],
        'daily_vol': round(daily_vol, 2),
        'avg_intra': round(avg_intra, 2),
        'top5': scored[:5],
        'all': scored,
    }


# ========== 报告输出 ==========

print(f"{'='*80}")
print(f"  历史回测报告：价值平均网格参数优化")
print(f"  回测区间: 40个交易日 | 目标市值: 每个10,000元")
print(f"  评分标准: 交易频率(6~24次) + 收益 + 胜率 - 最终偏差")
print(f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"{'='*80}")

all_results = {}
for code in ["003019", "513300", "161005", "159566", "159851"]:
    result = run_backtest(code)
    if result is None:
        print(f"\n✗ {code}: 数据加载失败")
        continue
    all_results[code] = result

    print(f"\n{'─'*80}")
    print(f"  {code} {result['name']}")
    print(f"  价格区间: {result['n_days']}天 | 最新 {result['latest_price']:.3f}")
    print(f"  日波动率: {result['daily_vol']:.2f}% | 日内振幅: {result['avg_intra']:.2f}%")
    print(f"{'─'*80}")
    print(f"  {'排名':>3} {'阈值%':>7} {'交易次数':>8} {'收益率%':>8} {'最终偏差%':>10} {'胜率':>6} {'评分':>6}")
    print(f"  {'-'*50}")
    for rank, (thr, trades, ret, dev, wr, score) in enumerate(result['top5']):
        rank_str = "🏆" if rank == 0 else f" {rank+1}"
        dev_str = f"{dev:+.2f}%"
        print(f"  {rank_str:>3} {thr:>6.1f}% {trades:>8} {ret:>+7.2f}% {dev_str:>10} {wr:>5.1f}% {score:>5.1f}")

    # 最优推荐
    best = result['top5'][0]
    thr_Z = round(best[0] / result['daily_vol'], 2) if result['daily_vol'] > 0 else 0
    print(f"\n  → 推荐最优阈值: ±{best[0]:.1f}% (Z={thr_Z:.2f}σ)")
    print(f"  → 40天预期交易: {best[1]}次 ({best[1]/8:.1f}次/周)")
    print(f"  → 理论预期: 0.6745×{result['daily_vol']:.2f}% = {0.6745*result['daily_vol']:.1f}%")

# 汇总对比
print(f"\n\n{'='*80}")
print(f"  最优参数汇总对比")
print(f"{'='*80}")
print(f"\n  {'标的':<8} {'名称':<14} {'日波动率':>9} {'最优阈值':>8} {'Z值':>6} {'交易/40天':>10} {'收益率':>8} {'最终偏差':>10}")
print(f"  {'-'*75}")
for code in ["003019", "513300", "161005", "159566", "159851"]:
    r = all_results.get(code)
    if not r: continue
    best = r['top5'][0]
    thr_Z = round(best[0] / r['daily_vol'], 2) if r['daily_vol'] > 0 else 0
    print(f"  {code:<8} {r['name']:<14} {r['daily_vol']:>8.2f}% {best[0]:>7.1f}% {thr_Z:>5.2f} {best[1]:>8}次 {best[2]:>+7.2f}% {best[3]:>+9.2f}%")

print(f"\n\n{'='*80}")
print(f"  结论")
print(f"{'='*80}")

# 对比理论最优
print(f"\n  理论阈值公式: threshold = Z × daily_vol, Z=0.6745（目标50%/天触发）")
print(f"  {'标的':<8} {'理论阈值':>8} {'回测最优':>8} {'差值':>6} {'理论触发/40天':>14} {'实际触发':>8}")
print(f"  {'-'*60}")
for code in ["003019", "513300", "161005", "159566", "159851"]:
    r = all_results.get(code)
    if not r: continue
    best = r['top5'][0]
    theoretical = round(0.6745 * r['daily_vol'], 1)
    # 理论触发：P(每天触发) = 2*(1-Φ(Z))
    z_act = theoretical / r['daily_vol'] if r['daily_vol'] > 0 else 0.6745
    p_daily = 2 * (1 - stats.norm.cdf(z_act)) if r['daily_vol'] > 0 else 0.5
    theoretical_trades = round(p_daily * 40)  # 40天
    diff = best[0] - theoretical
    diff_str = f"{diff:+.1f}%"
    print(f"  {code:<8} {theoretical:>7.1f}% {best[0]:>8.1f}% {diff_str:>6} {theoretical_trades:>10}次 {best[1]:>8}次")

recommendations = {}
for code in ["003019", "513300", "161005", "159566", "159851"]:
    r = all_results.get(code)
    if not r: continue
    best = r['top5'][0]
    theoretical = round(0.6745 * r['daily_vol'], 1)
    # 如果理论值和回测最优接近，用理论值(更普适)
    if abs(best[0] - theoretical) <= 0.3:
        rec = theoretical
    else:
        rec = best[0]
    recommendations[code] = rec

print(f"\n  最终推荐参数:")
for code in ["003019", "513300", "161005", "159566", "159851"]:
    r = all_results.get(code)
    print(f"  {code} {r['name']:<14} → ±{recommendations[code]:.1f}%  (回测{r['top5'][0][0]:.1f}% / 理论{r['daily_vol']*0.6745:.1f}%)")

# 保存结果
output = {
    'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
    'recommendations': recommendations,
    'details': {code: {
        'name': r['name'],
        'daily_vol': r['daily_vol'],
        'avg_intra': r['avg_intra'],
        'best_threshold': r['top5'][0][0],
        'best_trades': r['top5'][0][1],
        'best_return': r['top5'][0][2],
        'top5': [{'thr': x[0], 'trades': x[1], 'return': x[2], 'deviation': x[3], 'win_rate': x[4], 'score': x[5]}
                 for x in r['top5']],
    } for code, r in all_results.items()}
}

with open('/workspace/backtest_output/backtest_results.json', 'w') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
print(f"\n  详细结果已保存: /workspace/backtest_output/backtest_results.json")