import React from 'react';
import MicroLabel from './MicroLabel';

interface MetricCardProps {
  label: string;
  value: number | string;
  delta?: number;
  sparkline?: number[];
}

const MetricCard: React.FC<MetricCardProps> = ({ label, value, delta, sparkline }) => {
  const deltaClass = delta != null ? (delta >= 0 ? 'positive' : 'negative') : '';
  const deltaPrefix = delta != null ? (delta >= 0 ? '+' : '') : '';

  // Build inline SVG sparkline
  const renderSparkline = () => {
    if (!sparkline || sparkline.length < 2) return null;
    const w = 60;
    const h = 18;
    const max = Math.max(...sparkline, 1);
    const min = Math.min(...sparkline, 0);
    const range = max - min || 1;
    const stepX = w / (sparkline.length - 1);
    const points = sparkline.map((v, i) => {
      const x = i * stepX;
      const y = h - 2 - ((v - min) / range) * (h - 4);
      return `${x},${y}`;
    });

    return (
      <svg width={w} height={h} style={{ display: 'block', marginTop: 4 }}>
        <polyline
          points={points.join(' ')}
          fill="none"
          stroke="var(--vault-accent-dim)"
          strokeWidth="1"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    );
  };

  return (
    <div className="metric-card" style={{ padding: '8px' }}>
      <div className="metric-card-value">{value ?? '—'}</div>
      <div className="metric-card-label">
        <MicroLabel>{label}</MicroLabel>
      </div>
      {delta != null && (
        <div className={`metric-card-delta ${deltaClass}`}>
          {deltaPrefix}{delta}
        </div>
      )}
      {renderSparkline()}
    </div>
  );
};

export default MetricCard;
