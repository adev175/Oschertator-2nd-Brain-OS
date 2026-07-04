// Core data types for Oschertator 2nd Brain OS frontend

export interface VaultState {
  note_count: number;
  link_count: number;
  project_count: number;
  core_status: 'idle' | 'busy' | 'error';
  runner_alive: boolean;
  runner_status?: string;
  last_updated?: string;
  metrics?: Record<string, number>;
  directives?: string[];
  schedule?: ScheduledJob[];
  queue?: EnqueuedJob[];
}

export interface ScheduledJob {
  id: string;
  skill_id: string;
  cron: string;
  next_run?: string;
  last_run?: string;
  status: 'scheduled' | 'running' | 'completed' | 'failed';
}

export interface EnqueuedJob {
  id: string;
  skill_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  enqueued_at?: string;
}

export interface Job {
  id: string;
  skill_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress?: number;
  started_at?: string;
  finished_at?: string;
  output?: string;
  error?: string;
  enqueued_at?: string;
}

export interface Skill {
  id: string;
  name: string;
  description?: string;
  tags?: string[];
  category?: string;
  enabled?: boolean;
  icon?: string;
}

export interface GraphNode {
  id: string;
  title: string;
  folder: string;
  degree: number; // in + out
  inDegree: number;
  outDegree: number;
  tags?: string[];
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export interface GraphEdge {
  source: string;
  target: string;
  label?: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ExpreeNode {
  name: string;
  path: string;
  children?: ExpreeNode[];
  isDirectory: boolean;
  size?: number;
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool';
  content: string;
  tool_calls?: ToolCall[];
  tool_call_id?: string;
}

export interface ToolCall {
  id: string;
  type: string;
  function: {
    name: string;
    arguments: string;
  };
}

export interface ChatResponse {
  id: string;
  model: string;
  choices: {
    message: ChatMessage;
    finish_reason?: string;
  }[];
}

export interface SparklineDataPoint {
  value: number;
  label?: string;
}
