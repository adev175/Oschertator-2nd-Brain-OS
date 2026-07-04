import React from 'react';

const MicroLabel: React.FC<{
  children: React.ReactNode;
}> = ({ children }) => {
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        fontSize: '10px',
        fontFamily: 'var(--vault-font-mono)',
        fontWeight: 600,
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
        color: 'var(--vault-muted)',
      }}
    >
      <span style={{ color: 'var(--vault-accent)', fontSize: '8px' }}>▪</span>
      {children}
    </span>
  );
};

export default MicroLabel;
