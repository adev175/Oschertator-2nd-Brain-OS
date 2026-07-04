import React from 'react';
import MicroLabel from './MicroLabel';
import type { GraphData } from '../types';

interface CenterPanelProps {
  graphData: GraphData;
  directives?: string[];
  onPreview: (noteId: string, notePath?: string) => void;
}

const CenterPanel: React.FC<CenterPanelProps> = ({ graphData, directives, onPreview }) => {
  const primaryDirective = directives?.[0];

  return (
    <div className="center-panel">
      <GraphCanvas
        data={graphData}
        onNodeClick={onPreview}
      />
      {primaryDirective && (
        <div className="primary-directive">
          <div className="primary-directive-card">
            <div className="primary-directive-label">Primary Directive</div>
            <div className="primary-directive-text">{primaryDirective}</div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CenterPanel;
