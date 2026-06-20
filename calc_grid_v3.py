import json, math, statistics

with open("/workspace/mx_output/mx_data_159218_近60个交易日每日收盘价_开盘价_最高价_最低价_涨跌幅_raw.json") as f:
    data = json.load(f)

dto = data["data"]["data"]["searchDataResultDTO"]["dataTableDTOList"][0]
table = dto["table"]

def parse_price(v):
    if isinstance(v, str):
        return float(v.replace('元','').replace(',',''))
    return float(v)

close_key, high_key, low_key = "325898", "326339", "326386"

closes = [parse_price(v) for v in table[close_key]]
highs = [parse_price(v) for v in table[high_key]]
lows = [parse_price(v) for v in table[low_key]]

closes.reverse()
highs.reverse()
lows.reverse()

current_price = closes[-1]

# Recent 20-day stats
recent_n = 20
recent_highs = highs[-recent_n:]
recent_lows = lows[-recent_n:]
daily_ranges = [(recent_highs[i] - recent_lows[i]) for i in range(len(recent_highs))]
avg_daily_range = statistics.mean(daily_ranges)

print(f"当前价格: {current_price:.3f}")
print(f"近20日日均波幅: {avg_daily_range:.4f} ({avg_daily_range/current_price*100:.2f}%)")
print()

# Target: 2.5 trades/day
# Desired spacing = avg_daily_range / 2.5
target_spacing = avg_daily_range / 2.5
print(f"目标间距(2.5次/天): {target_spacing:.4f} ({target_spacing/current_price*100:.2f}%)")

# Use tight range around current price: recent 20-day high/low with 3% buffer
recent_20_low = min(recent_lows)
recent_20_high = max(recent_highs)
pct_buffer = 0.03
range_low = round(recent_20_low * (1 - pct_buffer), 3)
range_high = round(recent_20_high * (1 + pct_buffer), 3)
total_range = range_high - range_low

print(f"近期(20日)低点: {recent_20_low:.3f}, 高点: {recent_20_high:.3f}")
print(f"价格区间(含3%缓冲): {range_low:.3f} ~ {range_high:.3f}")
print()

# Calculate number of grids
num_grids = max(6, int(round(total_range / target_spacing)))
num_grids = min(num_grids, 14)
actual_spacing = total_range / num_grids
expected_trades = avg_daily_range / actual_spacing

# Adjust: if still not close to 2.5, tweak num_grids
while expected_trades < 2.0 and num_grids < 14:
    num_grids += 1
    actual_spacing = total_range / num_grids
    expected_trades = avg_daily_range / actual_spacing

while expected_trades > 3.5 and num_grids > 6:
    num_grids -= 1
    actual_spacing = total_range / num_grids
    expected_trades = avg_daily_range / actual_spacing

print(f"=== 网格参数设计 ===")
print(f"标的: 招商中证卫星产业ETF (159218)")
print(f"策略: 自适应网格 (基于近20日波动率)")
print(f"网格间距: {actual_spacing:.4f} 元 ({actual_spacing/current_price*100:.2f}%)")
print(f"网格数量: {num_grids}")
print(f"价格区间: {range_low:.3f} ~ {range_high:.3f}")
print(f"预期日均交易: {expected_trades:.1f}次")

print(f"\n=== 网格价格表 ===")
print(f"{'网格':>5} | {'价格':>8} | {'操作':>10}")
print("-" * 35)
grid_levels = []
for i in range(num_grids + 1):
    price = round(range_low + i * actual_spacing, 3)
    grid_levels.append(price)
    if price < current_price - actual_spacing/2:
        tag = "买入区"
    elif price > current_price + actual_spacing/2:
        tag = "卖出区"
    else:
        tag = "← 当前价"
    print(f"{i:>5} | {price:>8.3f} | {tag}")

current_idx = min(range(len(grid_levels)), key=lambda i: abs(grid_levels[i] - current_price))
print(f"\n当前价格 {current_price:.3f} 对应网格 {current_idx} ({grid_levels[current_idx]:.3f})")
print(f"底仓建仓: 网格0~{current_idx-1} 共{current_idx}格")

# Position
print(f"\n=== 仓位配置(假设10万元总资金) ===")
per_grid = 100000 / num_grids
shares = int(per_grid / current_price / 100) * 100
print(f"每格资金: {per_grid:.0f} 元")
print(f"每格数量: {shares} 份 (1手=100份)")
total_shares = shares * num_grids
print(f"最大持仓: {total_shares} 份")
print(f"最大资金占用: {total_shares * current_price:.0f} 元")
seed_shares = shares * current_idx
print(f"初始底仓: {seed_shares} 份 ≈ {seed_shares * current_price:.0f} 元")

print(f"\n=== 交易规则 ===")
print(f"- 价格上涨突破网格线 → 卖出1格({shares}份)")
print(f"- 价格下跌突破网格线 → 买入1格({shares}份)")
print(f"- 挂单间距: {actual_spacing:.4f}元")
print(f"- 数据源: 东方财富妙想金融数据(mx-data)")