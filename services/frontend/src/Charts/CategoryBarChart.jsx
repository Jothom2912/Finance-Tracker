
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';
import { formatAmount } from '../lib/formatters';
import { CHART_COLORS as COLORS } from '../lib/chartColors';

const formatCurrency = (value) => formatAmount(value, { decimals: 0 });

function CustomTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;

  const data = payload[0]?.payload;
  if (!data) return null;

  const hasBudget = data.budget > 0;
  const isOver = hasBudget && data.spent > data.budget;

  return (
    <div style={{
      backgroundColor: '#fff',
      padding: '12px 16px',
      border: '1px solid #e2e8f0',
      borderRadius: '8px',
      boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
      minWidth: '180px',
    }}>
      <p style={{ margin: '0 0 8px', fontWeight: 700, fontSize: '14px' }}>
        {data.name}
      </p>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', marginBottom: '4px' }}>
        <span style={{ color: '#64748b', fontSize: '13px' }}>Forbrug:</span>
        <span style={{ fontWeight: 600, fontSize: '13px' }}>{formatCurrency(data.spent)}</span>
      </div>
      {hasBudget && (
        <>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '16px', marginBottom: '4px' }}>
            <span style={{ color: '#64748b', fontSize: '13px' }}>Budget:</span>
            <span style={{ fontWeight: 600, fontSize: '13px' }}>{formatCurrency(data.budget)}</span>
          </div>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: '16px',
            paddingTop: '6px',
            borderTop: '1px solid #e2e8f0',
            marginTop: '4px',
          }}>
            <span style={{ color: isOver ? '#ef4444' : '#22c55e', fontSize: '13px', fontWeight: 600 }}>
              {isOver ? 'Over budget:' : 'Resterende:'}
            </span>
            <span style={{ fontWeight: 700, fontSize: '13px', color: isOver ? '#ef4444' : '#22c55e' }}>
              {formatCurrency(Math.abs(data.budget - data.spent))}
            </span>
          </div>
        </>
      )}
    </div>
  );
}

function CategoryBarChart({ categoryData, budgetItems }) {
  if (!categoryData || categoryData.length === 0) {
    return (
      <div className="chart-no-data">
        <p>Ingen data til diagram</p>
      </div>
    );
  }

  const chartData = categoryData.map((cat, index) => {
    const budgetInfo = budgetItems?.find((b) => b.category_id === cat.categoryId);
    const budget = budgetInfo?.budget_amount || 0;
    const spent = cat.value;
    const isOver = budget > 0 && spent > budget;

    return {
      name: cat.name.length > 18 ? cat.name.slice(0, 16) + '…' : cat.name,
      fullName: cat.name,
      spent,
      budget,
      color: cat.color || COLORS[index % COLORS.length],
      isOver,
    };
  });

  const maxValue = Math.max(
    ...chartData.map((d) => Math.max(d.spent, d.budget)),
  );

  const barHeight = 32;
  const chartHeight = Math.max(280, chartData.length * (barHeight + 16) + 60);

  return (
    <div style={{ width: '100%', height: chartHeight }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 8, right: 40, bottom: 8, left: 8 }}
          barGap={2}
          barSize={barHeight / 2}
        >
          <XAxis
            type="number"
            tickFormatter={formatCurrency}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: '#94a3b8' }}
            domain={[0, Math.ceil(maxValue * 1.1)]}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={130}
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 12, fill: '#334155', fontWeight: 500 }}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={{ fill: 'rgba(0,0,0,0.03)', radius: 4 }}
          />
          <ReferenceLine x={0} stroke="transparent" />

          <Bar dataKey="budget" name="Budget" radius={[4, 4, 4, 4]} fill="#e2e8f0" opacity={0.7}>
            {chartData.map((entry, index) => (
              <Cell
                key={`budget-${index}`}
                fill={entry.budget > 0 ? '#e2e8f0' : 'transparent'}
              />
            ))}
          </Bar>

          <Bar dataKey="spent" name="Forbrug" radius={[4, 4, 4, 4]}>
            {chartData.map((entry, index) => (
              <Cell
                key={`spent-${index}`}
                fill={entry.isOver ? '#ef4444' : entry.color}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export default CategoryBarChart;
