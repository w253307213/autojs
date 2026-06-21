#!/bin/bash
# 每日价值平均网格 — 自动执行脚本
# 由定时任务触发，每天15:30运行（A股收盘后）

export MX_APIKEY='mkt_k4G_Tse8OFGLi6WKBlOofot9VWIr3E4uG7FMtlf3QY0'
cd /workspace

echo "=== 每日价值平均网格 ===" > /workspace/value_avg_daily_report.txt
echo "运行时间: $(date '+%Y-%m-%d %H:%M')" >> /workspace/value_avg_daily_report.txt
echo "" >> /workspace/value_avg_daily_report.txt

# 用妙想获取各标的最新收盘价
python3 -c "
import os, re, subprocess, json
api_key = os.environ.get('MX_APIKEY','')
codes = ['003019','513300','161005','159566','159851']
prices = {}

for code in codes:
    try:
        r = subprocess.run(
            ['python3', 'mx_data.py', f'{code} 最新行情'],
            cwd='/root/.openclaw/workspace/skills/mx-data',
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'MX_APIKEY': api_key}
        )
        m = re.search(r'(?:最新|收盘)价[^\\d]*(\d+\.\d+)', r.stdout+r.stderr)
        if m: prices[code] = float(m.group(1))
    except: pass

with open('/workspace/current_prices.json','w') as f:
    json.dump(prices, f)
print('获取到的价格:', prices)
"

echo "" >> /workspace/value_avg_daily_report.txt

# 计算价值平均
python3 /workspace/daily_value_average.py << EOF  >> /workspace/value_avg_daily_report.txt 2>&1
$(python3 -c "
import json
with open('/workspace/current_prices.json') as f:
    p = json.load(f)
for k,v in p.items():
    print(v)
")
EOF

echo "" >> /workspace/value_avg_daily_report.txt
echo "=== 报告完成 ===" >> /workspace/value_avg_daily_report.txt

# 保存日志到日期目录
LOG_DIR="/workspace/value_avg_logs"
mkdir -p "$LOG_DIR"
cp /workspace/value_avg_daily_report.txt "$LOG_DIR/daily_$(date '+%Y%m%d').txt"

echo "报告已生成: /workspace/value_avg_daily_report.txt"
