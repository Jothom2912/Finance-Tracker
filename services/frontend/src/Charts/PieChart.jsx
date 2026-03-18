import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import { formatAmount } from '../lib/formatters';

const isDev = import.meta.env.DEV;

const CategoryPieChart = ({ data, colors }) => {
  if (!data || !Array.isArray(data) || data.length === 0) {
    if (isDev) console.warn('CategoryPieChart: Invalid or empty data provided');
    return (
      <div className="chart-no-data">
        <p>No data available for chart</p>
      </div>
    );
  }

  if (!colors || !Array.isArray(colors) || colors.length === 0) {
    if (isDev) console.warn('CategoryPieChart: Invalid or empty colors array provided');
    return (
      <div className="chart-error">
        <p>Chart configuration error</p>
      </div>
    );
  }

  const validData = data.every(item => 
    item && 
    typeof item === 'object' && 
    typeof item.name === 'string' && 
    typeof item.value === 'number' && 
    !isNaN(item.value) && 
    item.value > 0
  );

  if (!validData) {
    if (isDev) console.warn('CategoryPieChart: Invalid data structure');
    return (
      <div className="chart-error">
        <p>Invalid chart data structure</p>
      </div>
    );
  }

  // Custom tooltip formatter
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0];
      const value = data.value;
      const name = data.name;
      
      const formattedValue = formatAmount(value);

      return (
        <div className="custom-tooltip" style={{
          backgroundColor: '#fff',
          padding: '10px',
          border: '1px solid #ccc',
          borderRadius: '4px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <p style={{ margin: 0, fontWeight: 'bold' }}>{name}</p>
          <p style={{ margin: 0, color: '#666' }}>{formattedValue}</p>
        </div>
      );
    }
    return null;
  };

  // Custom label formatter
  const renderCustomizedLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, index, name }) => {
    // Only show labels for slices that are large enough (>5%)
    if (percent < 0.05) return null;

    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? 'start' : 'end'}
        dominantBaseline="central"
        fontSize="12"
        fontWeight="bold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  try {
    return (
      <div style={{ width: '100%', height: '400px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={renderCustomizedLabel}
              outerRadius={120}
              fill="#8884d8"
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={colors[index % colors.length]} 
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
    );
  } catch (error) {
    if (isDev) console.error('Error rendering PieChart:', error);
    return (
      <div className="chart-error">
        <p>Error rendering chart: {error.message}</p>
      </div>
    );
  }
};

export default CategoryPieChart;