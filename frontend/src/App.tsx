import React, { useState, useEffect, useCallback } from 'react';
import TopBar from './components/TopBar';
import LeftCol from './components/LeftCol';
import RightCol from './components/RightCol';
import CenterPanel from './components/CenterPanel';
import OschertatorWidget from './components/OschertatorWidget';
import PreviewOverlay from './components/PreviewOverlay';
import { fetchState, fetchSkills, fetchJobs, fetchGraph, fetchTree } from './utils/api';
import type { VaultState, Skill, Job, GraphData, ExpreeNode } from './types';

const App: React.FC = () => {
  const [vaultState, setVaultState] = useState<VaultState>({
    note_count: 0,
    link_count: 0,
    project_count: 0,
    core_status: 'idle',
    runner_alive: false,
  });
  const [skills, setSkills] = useState<Skill[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [tree, setTree] = useState<ExpreeNode[]>([]);
  const [previewNode, setPreviewNode] = useState<string | null>(null);
  const [previewPath, setPreviewPath] = useState<string | null>(null);

  // Poll vault state every 5s
  const loadState = useCallback(async () => {
    const state = await fetchState();
    setVaultState(state);
  }, []);

  useEffect(() => {
    loadState();
    const id = setInterval(loadState, 5000);
    return () => clearInterval(id);
  }, [loadState]);

  // Poll jobs every 3s
  const loadJobs = useCallback(async () => {
    const j = await fetchJobs();
    setJobs(j);
  }, []);

  useEffect(() => {
    loadJobs();
    const id = setInterval(loadJobs, 3000);
    return () => clearInterval(id);
  }, [loadJobs]);

  // One-time fetches on mount
  useEffect(() => {
    const init = async () => {
      const [s, g, t] = await Promise.all([fetchSkills(), fetchGraph(), fetchTree()]);
      setSkills(s);
      setGraphData(g);
      setTree(t);
    };
    void init();
  }, []);

  const handlePreview = useCallback((noteId: string, notePath?: string) => {
    setPreviewNode(noteId);
    if (notePath) {
      setPreviewPath(notePath);
    }
  }, []);

  const handlePreviewClose = useCallback(() => {
    setPreviewNode(null);
    setPreviewPath(null);
  }, []);

  return (
    <>
      <div className="app-container">
        <TopBar
          coreStatus={vaultState.core_status}
          runnerAlive={vaultState.runner_alive}
        />
        <LeftCol
          vaultState={vaultState}
          tree={tree}
          onPreview={handlePreview}
        />
        <CenterPanel
          graphData={graphData}
          directives={vaultState.directives}
          onPreview={handlePreview}
        />
        <RightCol
          skills={skills}
          jobs={jobs}
          schedule={vaultState.schedule}
          queue={vaultState.queue}
        />
      </div>
      <OschertatorWidget />
      {previewNode && (
        <PreviewOverlay
          noteId={previewNode}
          notePath={previewPath}
          onClose={handlePreviewClose}
        />
      )}
    </>
  );
};

export default App;
