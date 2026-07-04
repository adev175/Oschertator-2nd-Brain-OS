import type {
  VaultState,
  Job,
  Skill,
  GraphData,
  ExpreeNode,
  ChatMessage,
  ChatResponse,
} from '../types';

const API_BASE = '/api/vault';

async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Accept': 'application/json', 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API ${res.status} on ${path}`);
  }
  return res;
}

export async function fetchState(): Promise<VaultState> {
  try {
    const res = await apiFetch('/state');
    return res.json();
  } catch {
    return {
      note_count: 0,
      link_count: 0,
      project_count: 0,
      core_status: 'idle',
      runner_alive: false,
    };
  }
}

export async function fetchSkills(): Promise<Skill[]> {
  try {
    const res = await apiFetch('/skills');
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchJobs(): Promise<Job[]> {
  try {
    const res = await apiFetch('/jobs');
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchGraph(): Promise<GraphData> {
  try {
    const res = await apiFetch('/graph');
    return res.json();
  } catch {
    return { nodes: [], edges: [] };
  }
}

export async function fetchTree(): Promise<ExpreeNode[]> {
  try {
    const res = await apiFetch('/tree');
    return res.json();
  } catch {
    return [];
  }
}

export async function fetchFile(path: string): Promise<string> {
  try {
    const res = await apiFetch(`/file?path=${encodeURIComponent(path)}`);
    return res.text();
  } catch {
    return '';
  }
}

export async function enqueueJob(skillId: string): Promise<Job> {
  const res = await apiFetch('/jobs', {
    method: 'POST',
    body: JSON.stringify({ skill_id: skillId }),
  });
  return res.json();
}

export async function cancelJob(jobId: string): Promise<void> {
  await apiFetch(`/jobs/${jobId}/cancel`, { method: 'POST' });
}

export async function chat(
  message: string,
  history: ChatMessage[]
): Promise<ChatMessage> {
  try {
    const messages: ChatMessage[] = [
      { role: 'system', content: 'You are Oschertator, 2nd Brain Assistant' },
      ...history,
      { role: 'user', content: message },
    ];
    const res = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, model: 'default' }),
    });
    if (!res.ok) throw new Error(`Chat API ${res.status}`);

    const data: ChatResponse = await res.json();
    const choice = data.choices?.[0];
    if (choice?.message) {
      return choice.message;
    }
    return { role: 'assistant', content: '(no response)' };
  } catch {
    return { role: 'assistant', content: '(service unreachable)' };
  }
}
