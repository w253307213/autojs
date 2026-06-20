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

# Data is newest first, reverse to chronological
closes.reverse()
highs.reverse()
lows.reverse()

current_price = closes[-1]
print(f"当前价格: {current_price:.3f}")
print()

# Use recent 20-day data for more relevant volatility
recent_n = 20
recent_closes = closes[-recent_n:]
recent_highs = highs[-recent_n:]
recent_lows = lows[-recent_n:]

daily_ranges = [(recent_highs[i] - recent_lows[i]) for i in range(len(recent_highs))]
avg_daily_range_recent = statistics.mean(daily_ranges)
print(f"近{recent_n}日日均波幅: {avg_daily_range_recent:.4f} ({avg_daily_range_recent/current_price*100:.2f}%)")

# For 2.5 trades/day: grid_spacing = avg_range / 2.5
target_trades = 2.5
grid_spacing = avg_daily_range_recent / target_trades
print(f"目标交易次数: {target_trades}次/天")
print(f"计算网格间距: {grid_spacing:.4f} ({grid_spacing/current_price*100:.2f}%)")

# Set grid bounds based on current price +/- recent max daily range * 3
recent_max_range = max(daily_ranges)
buffer = recent_max_range * 3
lower_bound = round(current_price - buffer, 3)
upper_bound = round(current_price + buffer, 3)
# But also respect 60-day bounds (don't go too wide)
lower_bound = max(lower_bound, min(lows) * 0.97)
upper_bound = min(upper_bound, max(highs) * 1.03)
lower_bound = round(lower_bound, 3)
upper_bound = round(upper_bound, 3)

total_range = upper_bound - lower_bound
num_grids = max(5, int(round(total_range / grid_spacing)))
# Ensure reasonable number of grids
num_grids = min(num_grids, 15)

# Recalculate exact spacing
actual_spacing = total_range / num_grids
expected_trades = avg_daily_range_recent / actual_spacing

print(f"\n=== 网格参数 ===")
print(f"标的: 招商中证卫星产业ETF (159218)")
print(f"网格类型: 等间距自适应网格")
print(f"网格间距: {actual_spacing:.4f} 元 ({actual_spacing/current_price*100:.2f}%)")
print(f"网格数量: {num_grids}")
print(f"价格区间: {lower_bound:.3f} ~ {upper_bound:.3f}")
print(f"预期日均交易: {expected_trades:.1f}次")

print(f"\n=== 网格价格表 ===")
print(f"{'网格':>5} | {'价格':>8} | {'操作':>10}")
print("-" * 35)
grid_levels = []
for i in range(num_grids + 1):
    price = round(lower_bound + i * actual_spacing, 3)
    grid_levels.append(price)
    tag = ""
    if price < current_price - actual_spacing/2:
        tag = "买入"
    elif price > current_price + actual_spacing/2:
        tag = "卖出"
    else:
        tag = "当前价"
    print(f"{i:>5} | {price:>8.3f} | {tag}")

# Find current price position
current_grid_idx = min(range(len(grid_levels)), key=lambda i: abs(grid_levels[i] - current_price))
print(f"\n当前价格 {current_price:.3f} ≈ 网格{current_grid_idx}: {grid_levels[current_grid_idx]:.3f}")

# Position allocation (assuming 100,000 total capital)
print(f"\n=== 仓位配置(假设10万元) ===")
per_grid_capital = 100000 / num_grids
shares_per_grid = int(per_grid_capital / current_price / 100) * 100
print(f"每格资金: {per_grid_capital:.0f} 元")
print(f"每格数量: {shares_per_grid} 份")
print(f"基础底仓(网格{current_grid_idx}以下买入): {shares_per_grid * current_grid_idx} 份")
print(f"总资金占用(最大): {shares_per_grid * num_grids * current_price:.0f} 元")

print(f"\n=== 交易策略说明 ===")
print(f"价格每上涨{actual_spacing:.3f}元卖出1格")
print(f"价格每下跌{actual_spacing:.3f}元买入1格")
print(f"日内预期触发 {expected_trades:.1f} 次交易")
print(f"数据源: 东方财富妙想金融数据(mx-data)")