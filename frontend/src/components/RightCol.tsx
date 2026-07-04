import React from 'react';
import MicroLabel from './MicroLabel';
import MetricCard from './MetricCard';
import type { Skill, Job, ScheduledJob, EnqueuedJob } from '../types';
import { enqueueJob } from '../utils/api';

interface RightColProps {
  skills: Skill[];
  jobs: Job[];
  schedule?: ScheduledJob[];
  queue?: EnqueuedJob[];
}

const RightCol: React.FC<RightColProps> = ({ skills, jobs, schedule, queue }) => {
  const handleRunSkill = async (skillId: string) => {
    try {
      await enqueueJob(skillId);
    } catch {
      // Queue unreachable in dev
    }
  };

  const getJobStatusForId = (id: string) => {
    const job = jobs.find((j) => j.id === id);
    return job?.status || 'pending';
  };

  return (
    <div className="right-column">
      {/* Command Deck */}
      <div className="panel">
        <div className="panel-title">
          <MicroLabel>Command Deck</MicroLabel>
        </div>
        <div className="command-deck">
          {skills.length === 0 ? (
            <div className="empty-state">— no skills —</div>
          ) : (
            skills.map((skill) => (
              <button
                key={skill.id}
                className="skill-button"
                onClick={() => handleRunSkill(skill.id)}
                title={skill.description}
              >
                <span className="skill-button-icon">{getSkillIcon(skill.id)}</span>
                <span>{skill.name}</span>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Schedule */}
      <div className="panel">
        <div className="panel-title">
          <MicroLabel>Schedule</MicroLabel>
        </div>
        {!schedule || schedule.length === 0 ? (
          <div className="empty-state">— no schedule —</div>
        ) : (
          schedule.map((job) => (
            <div key={job.id} className="job-item">
              <span className={`job-item-status ${job.status}`} />
              <span style={{ flex: 1 }}>{job.skill_id}</span>
              <span style={{ opacity: 0.5 }}>{job.cron}</span>
              {job.next_run && (
                <span style={{ opacity: 0.4 }}>{formatTime(job.next_run)}</span>
              )}
            </div>
          ))
        )}
      </div>

      {/* Job Log */}
      <div className="panel">
        <div className="panel-title">
          <MicroLabel>Job Log</MicroLabel>
        </div>
        {jobs.length === 0 ? (
          <div className="empty-state">— no jobs —</div>
        ) : (
          jobs.slice(-8).map((job) => (
            <div key={job.id} className="job-item">
              <span className={`job-item-status ${getJobStatusForId(job.id)}`} />
              <span style={{ flex: 1 }}>{job.skill_id}</span>
              <span style={{ opacity: 0.4 }}>{job.status}</span>
            </div>
          ))
        )}
      </div>

      {/* Queue */}
      <div className="panel">
        <div className="panel-title">
          <MicroLabel>Queue</MicroLabel>
        </div>
        {(!queue || queue.length === 0) && !jobs.length ? (
          <div className="empty-state">— empty —</div>
        ) : (
          (queue || []).map((q) => (
            <div key={q.id} className="job-item">
              <span className={`job-item-status ${q.status}`} />
              <span style={{ flex: 1 }}>{q.skill_id}</span>
              {q.progress != null && q.progress > 0 && (
                <span style={{ opacity: 0.4 }}>{q.progress}%</span>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};

function getSkillIcon(id: string): string {
  const map: Record<string, string> = {
    parse: '📝',
    graph: '🔗',
    review: '📋',
    cleanup: '🧹',
    analyze: '📊',
    summarize: '📑',
    link: '🔗',
    metric: '📈',
    goal: '🎯',
    daily: '📅',
  };
  const parts = id.toLowerCase().split('-');
  for (const key of Object.keys(map)) {
    if (parts.includes(key)) return map[key];
  }
  return '⚡';
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  } catch {
    return '';
  }
}

export default RightCol;
