import React from 'react';
import MetricCard from './MetricCard';
import MicroLabel from './MicroLabel';
import type { VaultState, ExpreeNode } from '../types';

interface LeftColProps {
  vaultState: VaultState;
  tree: ExpreeNode[];
  onPreview: (noteId: string, notePath?: string) => void;
}

const LeftCol: React.FC<LeftColProps> = ({ vaultState, tree, onPreview }) => {
  // Render explorer tree items
  const renderTreeItem = (node: ExpreeNode, depth: number = 0) => {
    const indent = '\u00A0'.repeat(depth * 2);
    if (node.isDirectory) {
      return (
        <React.Fragment key={node.path}>
          <div className="explorer-item directory" style={{ paddingLeft: `${depth * 12 + 4}px` }}>
            <span style={{ opacity: 0.6, marginRight: 4 }}>{node.children ? '📂' : '📁'}</span>
            {node.name}
          </div>
          {node.children?.map((child) => renderTreeItem(child, depth + 1))}
        </React.Fragment>
      );
    }
    return (
      <div
        key={node.path}
        className="explorer-item"
        style={{ paddingLeft: `${depth * 12 + 4}px` }}
        onClick={() => onPreview(node.name, node.path)}
      >
        <span style={{ opacity: 0.5, marginRight: 4 }}>📄</span>
        {node.name}
      </div>
    );
  };

  return (
    <div className="left-column">
      {/* SystemVitals */}
      <div className="panel">
        <div className="panel-title">
          <MicroLabel>System Vitals</MicroLabel>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6, padding: '4px 0' }}>
          <MetricCard
            label="Notes"
            value={vaultState.note_count}
          />
          <MetricCard
            label="Links"
            value={vaultState.link_count}
          />
          <MetricCard
            label="Projects"
            value={vaultState.project_count}
          />
        </div>
        {vaultState.metrics && Object.keys(vaultState.metrics).length > 0 && (
          <div style={{ marginTop: 8, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
            {Object.entries(vaultState.metrics).slice(0, 4).map(([key, val]) => (
              <MetricCard key={key} label={key} value={val} />
            ))}
          </div>
        )}
      </div>

      {/* Explorer */}
      <div className="panel">
        <div className="panel-title">
          <MicroLabel>Explorer</MicroLabel>
        </div>
        <div style={{ maxHeight: 200, overflowY: 'auto' }}>
          {tree.length === 0 ? (
            <div className="empty-state">— no files —</div>
          ) : (
            tree.map((node) => renderTreeItem(node))
          )}
        </div>
      </div>

      {/* Directives */}
      <div className="panel">
        <div className="panel-title">
          <MicroLabel>Directives</MicroLabel>
        </div>
        {!vaultState.directives || vaultState.directives.length === 0 ? (
          <div className="empty-state">— no active directives —</div>
        ) : (
          vaultState.directives.map((d, i) => (
            <div key={i} className="directive-item">{d}</div>
          ))
        )}
      </div>

      {/* Documents */}
      <div className="panel">
        <div className="panel-title">
          <MicroLabel>Documents</MicroLabel>
        </div>
        <div style={{ maxHeight: 220, overflowY: 'auto' }}>
          {tree.length === 0 ? (
            <div className="empty-state">— no documents —</div>
          ) : (
            tree
              .filter((n) => !n.isDirectory)
              .slice(0, 10)
              .map((node) => (
                <div
                  key={node.path}
                  className="doc-item"
                  onClick={() => onPreview(node.name, node.path)}
                >
                  {node.name}
                </div>
              ))
          )}
        </div>
      </div>
    </div>
  );
};

export default LeftCol;
