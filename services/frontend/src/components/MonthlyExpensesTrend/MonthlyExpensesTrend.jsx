import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { formatAmount } from '../../lib/formatters';
import './MonthlyExpensesTrend.css';

const SHORT_MONTHS = [
  '', 'Jan', 'Feb', 'Mar', 'Apr', 'Maj', 'Jun',
  'Jul', 'Aug', 'Sep', 'Okt', 'Nov', 'Dec',
];

// Serie-farver: valideret par (CVD ΔE 21.3 mod hvid surface) — identitet
// bæres desuden af legend + tooltip, aldrig farve alene.
const INCOME_COLOR = 'var(--color-success-500)';
const EXPENSE_COLOR = 'var(--color-error-500)';

function labelFromMonthKey(monthKey) {
  // "YYYY-MM" (budgetmåned fra serveren) → "Maj 26"
  const [year, month] = monthKey.split('-').map(Number);
  return `${SHORT_MONTHS[month]} ${String(year).slice(2)}`;
}

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const data = payload[0]?.payload;
  if (!data) return null;

  return (
    <div className="monthly-trend-tooltip">
      <p className="monthly-trend-tooltip-title">{data.label}</p>
      <p className="monthly-trend-tooltip-row">
        <span className="monthly-trend-dot income" aria-hidden="true" />
        Indtægter: {formatAmount(data.totalIncome)}
      </p>
      <p className="monthly-trend-tooltip-row">
        <span className="monthly-trend-dot expense" aria-hidden="true" />
        Udgifter: {formatAmount(data.totalExpenses)}
      </p>
      <p className="monthly-trend-tooltip-net">
        Netto: {formatAmount(data.net)}
      </p>
    </div>
  );
}

function MonthlyExpensesTrend({ data, averageMonthlyExpenses }) {
  // Serveren leverer et dense, kronologisk vindue af budgetmåneder —
  // ingen klient-side zero-fill eller vindueslogik.
  const chartData = (data ?? []).map((row) => ({
    ...row,
    label: labelFromMonthKey(row.month),
  }));

  const hasActivity = chartData.some((r) => r.totalIncome !== 0 || r.totalExpenses !== 0);

  if (!hasActivity) {
    return (
      <div className="monthly-trend-section">
        <div className="monthly-trend-header">
          <h3>Indtægter og udgifter over tid</h3>
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
        <h3>Indtægter og udgifter over tid</h3>
      </div>
      <div className="monthly-trend-chart">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 16, bottom: 0, left: 0 }} barGap={2}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--color-border-light)"
              vertical={false}
            />
            <XAxis
              dataKey="label"
              axisLine={false}
              tickLine={false}
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              interval="preserveStartEnd"
            />
            <YAxis
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => formatAmount(v, { decimals: 0 })}
              tick={{ fontSize: 11, fill: 'var(--color-text-muted)' }}
              width={80}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'var(--color-border-light)', opacity: 0.35 }} />
            <Legend
              formatter={(value) => (
                <span style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>{value}</span>
              )}
              iconType="circle"
              iconSize={8}
            />
            {averageMonthlyExpenses > 0 && (
              <ReferenceLine
                y={averageMonthlyExpenses}
                stroke="var(--color-text-muted)"
                strokeDasharray="6 4"
                strokeWidth={1.5}
                label={{
                  value: 'Gns. udgifter',
                  position: 'insideTopRight',
                  fontSize: 11,
                  fill: 'var(--color-text-muted)',
                }}
              />
            )}
            <Bar
              dataKey="totalIncome"
              name="Indtægter"
              fill={INCOME_COLOR}
              radius={[4, 4, 0, 0]}
              maxBarSize={18}
            />
            <Bar
              dataKey="totalExpenses"
              name="Udgifter"
              fill={EXPENSE_COLOR}
              radius={[4, 4, 0, 0]}
              maxBarSize={18}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

export default MonthlyExpensesTrend;
