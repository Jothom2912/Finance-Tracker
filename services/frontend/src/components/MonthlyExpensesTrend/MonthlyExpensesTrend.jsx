import { useMemo } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { formatAmount, getMonthName } from '../../lib/formatters';
import './MonthlyExpensesTrend.css';

const SHORT_MONTHS = [
  '', 'Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun',
  'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec',
];

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div style={{
      background: 'var(--color-bg-surface)',
      padding: '10px 14px',
      border: '1px solid var(--color-border-light)',
      borderRadius: 'var(--radius-md)',
      boxShadow: 'var(--shadow-md)',
    }}>
      <p style={{ margin: 0, fontWeight: 600, fontSize: '13px' }}>
        {data.label}
      </p>
      <p style={{ margin: '4px 0 0', fontSize: '13px', color: 'var(--color-error-500)' }}>
        {formatAmount(data.totalExpenses)}
      </p>
    </div>
  );
}

function MonthlyExpensesTrend({ data }) {
  const chartData = useMemo(() => {
    if (!data || data.length === 0) return [];

    const now = new Date();
    const months = [];
    for (let i = 5; i >= 0; i--) {
      const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
      months.push({
        month: key,
        label: `${SHORT_MONTHS[d.getMonth() + 1]} ${d.getFullYear()}`,
        shortLabel: SHORT_MONTHS[d.getMonth() + 1],
        totalExpenses: 0,
      });
    }

    const dataMap = {};
    for (const item of data) {
      dataMap[item.month] = item.totalExpenses;
    }

    return months.map((m) => ({
      ...m,
      totalExpenses: dataMap[m.month] || 0,
    }));
  }, [data]);

  if (chartData.length === 0) {
    return (
      <div className="monthly-trend-section">
        <div className="monthly-trend-header">
          <h3>Udgifter over tid</h3>
        </div>
        <div className="monthly-trend-empty">
          <p>Ingen data til trend endnu.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="monthly-trend-section">
      <div className="monthly-trend-header">
        <h3>Udgifter over tid</h3>
      </div>
      <div className="monthly-trend-chart">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="expenseGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="var(--color-error-500)" stopOpacity={0.15} />
                <stop offset="95%" stopColor="var(--color-error-500)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--color-border-light)"
              vertical={false}
            />
            <XAxis
              dataKey="shortLabel"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 12, fill: 'var(--color-text-muted)' }}
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => formatAmount(v, { decimals: 0 })}
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              width={80}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="totalExpenses"
              stroke="var(--color-error-500)"
              strokeWidth={2}
              fill="url(#expenseGradient)"
              dot={{ r: 4, fill: 'var(--color-error-500)', strokeWidth: 0 }}
              activeDot={{ r: 6, stroke: 'var(--color-bg-surface)', strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default MonthlyExpensesTrend;
