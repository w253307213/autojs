// assets/charts.js
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var accent3 = style.getPropertyValue('--accent3').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  // --- Chart: Threshold Comparison ---
  var codes = ['003019', '513300', '161005', '159566', '159851'];
  var names = ['宸展光电', '纳指100ETF', '富国天惠', '电池ETF', '金融科技'];
  var dailyVol = [4.34, 1.95, 1.09, 2.29, 1.99];
  var theoreticalThr = [2.9, 1.3, 0.7, 1.5, 1.3];
  var backtestThr = [5.0, 4.6, 5.0, 4.4, 3.8];
  var backtestTrades = [1, 8, 2, 7, 7];

  var chart1 = echarts.init(document.getElementById('chart-threshold'), null, { renderer: 'svg' });
  chart1.setOption({
    tooltip: {
      trigger: 'axis',
      appendToBody: true,
      formatter: function(params) {
        var s = '<b>' + params[0].axisValue + '</b><br>';
        params.forEach(function(p) {
          s += p.marker + ' ' + p.seriesName + ': ' + p.value + (p.seriesName.indexOf('率') >= 0 ? '%' : '次') + '<br>';
        });
        return s;
      }
    },
    legend: {
      data: ['日波动率', '理论阈值(推荐)', '回测最优阈值', '回测交易次数'],
      textStyle: { color: muted, fontSize: 11 },
      top: 0
    },
    grid: { top: 45, bottom: 20, left: 60, right: 50 },
    xAxis: {
      type: 'category',
      data: codes.map(function(c, i) { return c + ' ' + names[i]; }),
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: [
      {
        type: 'value',
        name: '%',
        nameTextStyle: { color: muted, fontSize: 10 },
        axisLabel: { color: muted },
        splitLine: { lineStyle: { color: rule, type: 'dashed' } },
        axisLine: { show: false }
      },
      {
        type: 'value',
        name: '交易次数',
        nameTextStyle: { color: muted, fontSize: 10 },
        axisLabel: { color: muted },
        splitLine: { show: false },
        axisLine: { show: false },
        min: 0
      }
    ],
    series: [
      {
        name: '日波动率',
        type: 'bar',
        barWidth: 14,
        itemStyle: { color: muted + '66' },
        data: dailyVol
      },
      {
        name: '理论阈值(推荐)',
        type: 'bar',
        barWidth: 14,
        itemStyle: { color: accent },
        data: theoreticalThr
      },
      {
        name: '回测最优阈值',
        type: 'bar',
        barWidth: 14,
        itemStyle: { color: accent2 },
        data: backtestThr
      },
      {
        name: '回测交易次数',
        type: 'line',
        yAxisIndex: 1,
        lineStyle: { color: accent3, width: 2 },
        itemStyle: { color: accent3 },
        symbol: 'circle',
        symbolSize: 8,
        data: backtestTrades
      }
    ]
  });
  window.addEventListener('resize', function() { chart1.resize(); });
})();