import React, { useState, useEffect, useRef } from 'react';
import MarkdownIt from 'markdown-it';
import { fetchFile } from '../utils/api';
import type { GraphData } from '../types';

interface PreviewOverlayProps {
  noteId: string;
  notePath?: string | null;
  onClose: () => void;
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  typographer: true,
});

/* Render [[wikilink]] as accent-colored links */
const mdRender = (raw: string): string => {
  const links = raw.replace(/\[\[([^\]]+)\]\]/g, (match, link) => {
    const id = encodeURIComponent(link);
    return `<a class="wiki-link" data-wiki-ref="${id}">${link}</a>`;
  });

  const rendered: string = md.render(links);
  return rendered;
};

const PreviewOverlay: React.FC<PreviewOverlayProps> = ({ noteId, notePath, onClose }) => {
  const [raw, setRaw] = useState('');
  const [loading, setLoading] = useState(true);
  const [backlinks, setBacklinks] = useState<string[]>([]);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const content = await fetchFile(notePath || noteId);
      setRaw(content || `# ${noteId}\n\n_(content unavailable)_`);
      setLoading(false);
    };
    void load();
  }, [noteId, notePath]);

  /* Find backlinks by scanning for [[noteId]] in content */
  useEffect(() => {
    if (raw) {
      const refs: string[] = [];
      const wikiPattern = /\[\[([^\]]+)\]\]/g;
      let m;
      while ((m = wikiPattern.exec(raw)) !== null) {
        refs.push(m[1]);
      }
      setBacklinks(refs);
    }
  }, [raw, noteId]);

  const rendered = mdRender(raw);

  /* Handle wikilink clicks */
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (target.classList.contains('wiki-link')) {
        e.preventDefault();
      }
    };
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) onClose();
  };

  return (
    <div className="preview-overlay" onClick={handleBackdropClick}>
      <div className="preview-panel" onClick={(e) => e.stopPropagation()}>
        <button className="preview-overlay-close" onClick={onClose}>
          ✕
        </button>
        <div className="preview-header">
          {loading ? 'Loading...' : noteId}
        </div>
        <div
          className="preview-content"
          dangerouslySetInnerHTML={{ __html: rendered }}
        />
        {backlinks.length > 0 && (
          <div className="backlinks-section">
            <strong>Backlinks:</strong>{' '}
            {backlinks.map((ref, i) => (
              <React.Fragment key={i}>
                {i > 0 && ', '}
                <span className="wiki-link">{ref}</span>
              </React.Fragment>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default PreviewOverlay;
