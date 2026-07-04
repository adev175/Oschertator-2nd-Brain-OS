import React, { useState, useEffect } from 'react';
import StatusPill from './StatusPill';

const TopBar: React.FC<{
  coreStatus: string;
  runnerAlive: boolean;
}> = ({ coreStatus, runnerAlive }) => {
  const [clock, setClock] = useState('—');

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      const h = String(now.getHours()).padStart(2, '0');
      const m = String(now.getMinutes()).padStart(2, '0');
      const s = String(now.getSeconds()).padStart(2, '0');
      setClock(`${h}:${m}:${s}`);
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="top-bar">
      <div className="top-bar-title">OSCHERTATOR</div>
      <div className="top-bar-status">
        <StatusPill
          label={`CORE ${coreStatus.toUpperCase()}`}
          status={coreStatus === 'idle' || coreStatus === 'busy' ? 'ok' : 'error'}
        />
        <StatusPill
          label={`RUNNER ${runnerAlive ? 'ALIVE' : 'DEAD'}`}
          status={runnerAlive ? 'ok' : 'error'}
        />
      </div>
      <div className="top-bar-clock">{clock}</div>
    </header>
  );
};

export default TopBar;
