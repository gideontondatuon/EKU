'use strict';
document.addEventListener('DOMContentLoaded', () => {
  const menu = document.querySelector('[data-menu-toggle]');
  const sidebar = document.getElementById('admin-sidebar');
  if (menu && sidebar) {
    menu.addEventListener('click', () => {
      const expanded = menu.getAttribute('aria-expanded') === 'true';
      menu.setAttribute('aria-expanded', String(!expanded));
      sidebar.classList.toggle('is-open', !expanded);
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        sidebar.classList.remove('is-open');
        menu.setAttribute('aria-expanded', 'false');
      }
    });
    document.addEventListener('click', (event) => {
      if (!sidebar.contains(event.target) && !menu.contains(event.target)) {
        sidebar.classList.remove('is-open');
        menu.setAttribute('aria-expanded', 'false');
      }
    });
  }
  document.querySelectorAll('form[data-confirm]').forEach((form) => {
    form.addEventListener('submit', (event) => {
      const selected = form.querySelectorAll('input[name="ids"]');
      if (selected.length && !Array.from(selected).some((input) => input.checked)) {
        event.preventDefault();
        window.alert('Pilih setidaknya satu transaksi terlebih dahulu.');
        return;
      }
      const count = Array.from(selected).filter((input) => input.checked).length;
      const message = form.dataset.confirm + (count ? '\nJumlah transaksi dipilih: ' + count : '');
      if (!window.confirm(message)) event.preventDefault();
    });
  });
  document.querySelectorAll('[data-select-all]').forEach((control) => {
    control.addEventListener('change', () => {
      control.closest('form').querySelectorAll('input[name="ids"]').forEach((input) => { input.checked = control.checked; });
    });
  });
  document.querySelectorAll('[data-period-filter]').forEach((form) => {
    const period = form.querySelector('select[name="period"]');
    if (!period) return;
    const updatePeriod = () => {
      form.querySelectorAll('[data-period]').forEach((field) => {
        const active = field.dataset.period === period.value;
        field.hidden = !active;
        field.querySelectorAll('input').forEach((input) => { input.disabled = !active; });
      });
    };
    period.addEventListener('change', updatePeriod);
    updatePeriod();
  });
  if (!window.echarts) return;
  const charts = [];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const money = new Intl.NumberFormat('id-ID', { style: 'currency', currency: 'IDR', maximumFractionDigits: 0 });
  const axisMoney = (value) => {
    const abs = Math.abs(value);
    if (abs >= 1e12) return (value / 1e12).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + ' T';
    if (abs >= 1e9) return (value / 1e9).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + ' Miliar';
    if (abs >= 1e6) return (value / 1e6).toLocaleString('id-ID', { maximumFractionDigits: 1 }) + ' Juta';
    return value.toLocaleString('id-ID');
  };
  function draw(containerId, sourceId, labelKey, chartType) {
    const container = document.getElementById(containerId);
    const source = document.getElementById(sourceId);
    if (!container || !source) return;
    let rows;
    try { rows = JSON.parse(source.textContent); } catch (_) { return; }
    if (!Array.isArray(rows) || !rows.length) return;
    const chart = window.echarts.init(container, null, { renderer: 'svg' });
    const type = chartType || container.dataset.chart || 'bar';
    const series = [
      { key: 'inflow', name: 'Inflow', color: '#1976E9' },
      { key: 'outflow', name: 'Outflow', color: '#CE8734' }
    ].map((item) => ({
      name: item.name, type, data: rows.map((row) => row[item.key] == null ? null : Number(row[item.key])),
      itemStyle: { color: item.color, borderRadius: type === 'bar' ? [3, 3, 0, 0] : 0 },
      barMaxWidth: 38, barGap: '18%', lineStyle: { width: 3 }, symbol: 'circle', symbolSize: 6,
      connectNulls: false, emphasis: { focus: 'series' }
    }));
    chart.setOption({
      animation: !reducedMotion,
      aria: { enabled: true, decal: { show: false } },
      textStyle: { fontFamily: 'Plus Jakarta Sans, sans-serif', fontSize: 11, color: '#64778B' },
      grid: { top: 35, left: 22, right: 20, bottom: 25, containLabel: true },
      tooltip: { trigger: 'axis', renderMode: 'richText', valueFormatter: (value) => value == null ? 'Tidak tersedia' : money.format(value), backgroundColor: '#fff', borderColor: '#dfe7ef', padding: 12 },
      xAxis: { type: 'category', data: rows.map((row) => String(row[labelKey] ?? '')), axisLine: { lineStyle: { color: '#DCE4ED' } }, axisTick: { show: false }, axisLabel: { margin: 15, hideOverlap: true } },
      yAxis: { type: 'value', axisLabel: { formatter: axisMoney }, splitLine: { lineStyle: { color: '#EDF1F6', type: 'dashed' } } },
      series
    });
    charts.push(chart);
  }
  draw('cashflow-chart', 'cashflow-series', 'period');
  draw('denomination-chart', 'denomination-series', 'denomination', 'bar');
  draw('seasonality-chart', 'seasonality-series', 'month', 'bar');
  if ('ResizeObserver' in window) {
    charts.forEach((chart) => new ResizeObserver(() => chart.resize()).observe(chart.getDom()));
  } else {
    window.addEventListener('resize', () => charts.forEach((chart) => chart.resize()));
  }
});
