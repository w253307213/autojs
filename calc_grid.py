import json, math, statistics

with open("/workspace/mx_output/mx_data_159218_近60个交易日每日收盘价_开盘价_最高价_最低价_涨跌幅_raw.json") as f:
    data = json.load(f)

dto = data["data"]["data"]["searchDataResultDTO"]["dataTableDTOList"][0]
table = dto["table"]
dates = table["headName"]

def parse_price(v):
    if isinstance(v, str):
        return float(v.replace('元','').replace(',',''))
    return float(v)

close_key = "325898"
high_key = "326339"
low_key = "326386"
open_key = "326269"

closes = [parse_price(v) for v in table[close_key]]
highs = [parse_price(v) for v in table[high_key]]
lows = [parse_price(v) for v in table[low_key]]
opens = [parse_price(v) for v in table[open_key]]

# Reverse to chronological order (data is newest first)
closes.reverse()
highs.reverse()
lows.reverse()
opens.reverse()
dates_rev = list(reversed(dates))

print(f"数据天数: {len(closes)}")
print(f"最新价: {closes[-1]:.3f}")
print(f"60日最高: {max(highs):.3f}")
print(f"60日最低: {min(lows):.3f}")
print(f"60日均价: {statistics.mean(closes):.3f}")

# Daily ranges
daily_ranges = [(h - l) for h, l in zip(highs, lows)]
avg_daily_range = statistics.mean(daily_ranges)
print(f"\n=== 波动性分析 ===")
print(f"日均波幅(高-低): {avg_daily_range:.4f}")
print(f"日均波幅%: {avg_daily_range / statistics.mean(closes) * 100:.2f}%")
print(f"最大日波幅: {max(daily_ranges):.4f}")
print(f"最小日波幅: {min(daily_ranges):.4f}")
print(f"日波幅标准差: {statistics.stdev(daily_ranges):.4f}")

# Price change % day over day
daily_changes = [(closes[i] - closes[i-1]) / closes[i-1] * 100 for i in range(1, len(closes))]
avg_daily_change = statistics.mean([abs(c) for c in daily_changes])
print(f"日均涨跌幅(绝对值): {avg_daily_change:.2f}%")

# Current price
current_price = closes[-1]
center_price = round(current_price, 3)

# Grid design: aim for 2-3 trades per day
# Grid spacing should be about 1/3 to 1/2 of average daily range
# So that price moves across ~2-3 grid levels per day
grid_spacing_price = round(avg_daily_range / 2.5, 3)
grid_spacing_pct = round(grid_spacing_price / center_price * 100, 3)

print(f"\n=== 网格参数设计 ===")
print(f"当前价格: {center_price:.3f}")
print(f"单格间距: {grid_spacing_price:.3f} 元 ({grid_spacing_pct:.3f}%)")

# Determine grid bounds: use recent 60-day range
upper_bound = max(highs)
lower_bound = min(lows)
# Add 5% buffer
mid = (upper_bound + lower_bound) / 2
half_range = (upper_bound - lower_bound) / 2 * 1.05
upper_bound = round(mid + half_range, 3)
lower_bound = round(mid - half_range, 3)

print(f"上边界: {upper_bound:.3f}")
print(f"下边界: {lower_bound:.3f}")
print(f"价格区间: {upper_bound - lower_bound:.3f}")

# Number of grids
total_range = upper_bound - lower_bound
num_grids = max(5, int(total_range / grid_spacing_price))
num_grids = min(num_grids, 12)  # cap at 12

print(f"网格数量: {num_grids}")

# Recalculate spacing based on number of grids
actual_spacing = total_range / num_grids
print(f"实际网格间距: {actual_spacing:.4f} 元 ({actual_spacing/center_price*100:.3f}%)")

# Expected trades per day
# Each time price moves through one grid level, it generates a trade
# Expected trades per day = avg_daily_range / actual_spacing
expected_trades = avg_daily_range / actual_spacing
print(f"预期日交易次数: {expected_trades:.1f}次")

# Generate grid levels
print(f"\n=== 网格价格表 ===")
print(f"{'网格':>5} | {'价格':>8} | {'买入/卖出':>10}")
print("-" * 35)
grid_levels = []
for i in range(num_grids + 1):
    price = round(lower_bound + i * actual_spacing, 3)
    grid_levels.append(price)
    tag = "基准" if abs(price - center_price) < actual_spacing / 2 else ""
    print(f"{i:>5} | {price:>8.3f} | {tag}")

# Find which grid the current price is in
current_grid_idx = min(range(len(grid_levels)), key=lambda i: abs(grid_levels[i] - current_price))
print(f"\n当前价格 {current_price:.3f} 落在网格 {current_grid_idx} 附近")

# Position allocation suggestion
print(f"\n=== 仓位配置建议(假设总资金10万元) ===")
per_grid_capital = 100000 / num_grids
print(f"每格资金: {per_grid_capital:.0f} 元")
print(f"每格买入数量: 约 {int(per_grid_capital / current_price / 100) * 100} 份 (按100份整数倍)")
print(f"\n=== 网格参数总结 ===")
print(f"标的: 招商中证卫星产业ETF (159218)")
print(f"网格类型: 等间距网格")
print(f"网格间距: {actual_spacing:.3f} 元 ({actual_spacing/center_price*100:.2f}%)")
print(f"网格数量: {num_grids}")
print(f"价格区间: {lower_bound:.3f} ~ {upper_bound:.3f}")
print(f"预期日均交易: {expected_trades:.1f}次")
print(f"触发条件: 价格每穿过一个网格间距触发一次交易")
print(f"数据源: 东方财富妙想金融数据")