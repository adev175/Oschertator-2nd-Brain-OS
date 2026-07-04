import React from 'react';

const StatusPill: React.FC<{
  label: string;
  status: 'ok' | 'error' | 'warn';
}> = ({ label, status }) => {
  const colorMap = {
    ok: 'var(--vault-accent)',
    error: 'var(--vault-danger)',
    warn: '#e8a500',
  } as const;

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: '2px 8px',
        borderRadius: '10px',
        fontSize: '10px',
        fontFamily: 'var(--vault-font-mono)',
        fontWeight: 600,
        letterSpacing: '0.05em',
        background: `${colorMap[status]}18`,
        border: `1px solid ${colorMap[status]}44`,
        color: colorMap[status],
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: colorMap[status],
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
      {label}
    </span>
  );
};

export default StatusPill;
