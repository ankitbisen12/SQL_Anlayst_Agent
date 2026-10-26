import {
  Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis,
} from 'recharts'
import { formatCompact, formatValue, humanize } from '../format'

// Categorical slots in fixed order (validated palette, defined per theme in styles.css).
const SERIES = Array.from({ length: 8 }, (_, i) => `var(--series-${i + 1})`)

const axisProps = {
  tick: { fill: 'var(--text-muted)', fontSize: 12 },
  axisLine: { stroke: 'var(--border)' },
  tickLine: false,
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="chart-tooltip">
      {label !== undefined && <div className="chart-tooltip-label">{formatValue(label)}</div>}
      {payload.map((p) => (
        <div key={p.dataKey ?? p.name} className="chart-tooltip-row">
          <span className="swatch" style={{ background: p.color || p.payload?.fill }} />
          <span>{humanize(p.name)}</span>
          <strong>{formatValue(p.value)}</strong>
        </div>
      ))}
    </div>
  )
}

const legendFormatter = (v) => <span className="legend-text">{humanize(v)}</span>

export default function ChartView({ chart, result }) {
  const data = result.rows.map((row) => Object.fromEntries(result.columns.map((c, i) => [c, row[i]])))
  const { type, x, y = [] } = chart
  const many = data.length > 6
  const legend = y.length > 1 ? <Legend itemSorter={null} formatter={legendFormatter} iconType="circle" iconSize={8} /> : null

  let body
  if (type === 'bar') {
    body = (
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barGap={2} barCategoryGap="22%">
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey={x} {...axisProps} interval={0} angle={many ? -30 : 0}
          textAnchor={many ? 'end' : 'middle'} height={many ? 72 : 32} />
        <YAxis {...axisProps} tickFormatter={formatCompact} width={52} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: 'var(--hover)' }} />
        {legend}
        {y.map((key, i) => (
          <Bar key={key} dataKey={key} fill={SERIES[i]} radius={[4, 4, 0, 0]} maxBarSize={44} animationDuration={500} />
        ))}
      </BarChart>
    )
  } else if (type === 'line') {
    body = (
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey={x} {...axisProps} minTickGap={28} />
        <YAxis {...axisProps} tickFormatter={formatCompact} width={52} />
        <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--text-muted)', strokeDasharray: '3 3' }} />
        {legend}
        {y.map((key, i) => (
          <Line key={key} type="monotone" dataKey={key} stroke={SERIES[i]} strokeWidth={2} animationDuration={500}
            dot={data.length <= 24 ? { r: 3, strokeWidth: 0, fill: SERIES[i] } : false}
            activeDot={{ r: 5, stroke: 'var(--surface)', strokeWidth: 2 }} />
        ))}
      </LineChart>
    )
  } else if (type === 'pie') {
    body = (
      <PieChart>
        <Tooltip content={<ChartTooltip />} />
        <Legend itemSorter={null} formatter={(v) => <span className="legend-text">{formatValue(v)}</span>} iconType="circle" iconSize={8} />
        <Pie data={data} dataKey={y[0]} nameKey={x} innerRadius="58%" outerRadius="86%" startAngle={90} endAngle={-270}
          paddingAngle={1} stroke="var(--surface)" strokeWidth={2} animationDuration={500}>
          {data.map((_, i) => <Cell key={i} fill={SERIES[i % SERIES.length]} />)}
        </Pie>
      </PieChart>
    )
  } else if (type === 'scatter') {
    body = (
      <ScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="var(--grid)" />
        <XAxis type="number" dataKey={x} name={x} {...axisProps} tickFormatter={formatCompact} />
        <YAxis type="number" dataKey={y[0]} name={y[0]} {...axisProps} tickFormatter={formatCompact} width={52} />
        <Tooltip content={<ChartTooltip />} />
        <Scatter data={data} fill={SERIES[0]} stroke="var(--surface)" strokeWidth={1} />
      </ScatterChart>
    )
  } else {
    return null
  }

  return (
    <figure className="chart" aria-label={`${type} chart of ${y.map(humanize).join(', ')} by ${humanize(x)}`}>
      <ResponsiveContainer width="100%" height={300}>{body}</ResponsiveContainer>
    </figure>
  )
}
