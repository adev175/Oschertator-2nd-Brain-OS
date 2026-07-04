import React, { useState, useRef, useEffect, useCallback } from 'react';
import type { ChatMessage } from '../types';
import { chat as apiChat } from '../utils/api';

const STORAGE_KEY = 'oschertor_chat_history';

const OschertatorWidget: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
    } catch {
      // storage full or unavailable
    }
  }, [messages]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    if (open && inputRef.current) {
      inputRef.current.focus();
    }
  }, [open]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || typing) return;

    const userMsg: ChatMessage = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setTyping(true);

    const history = messages.filter((m) => m.role === 'user' || m.role === 'assistant');
    const response = await apiChat(text, history);

    setMessages((prev) => [...prev, response]);
    setTyping(false);
  }, [input, typing, messages]);

  const handleClear = useCallback(() => {
    setMessages([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void handleSend();
    }
  }, [handleSend]);

  const toggleOpen = useCallback(() => setOpen((prev) => !prev), []);

  /* Message rendering */
  const renderMessage = (msg: ChatMessage, idx: number) => {
    const content = msg.content || '';

    if (msg.role === 'tool' && msg.tool_call_id) {
      return (
        <div key={idx} className="oschertator-msg tool">
          ⚙ tool call: {msg.tool_call_id}
        </div>
      );
    }

    if (msg.role === 'user') {
      return (
        <div key={idx} className="oschertator-msg user">
          {content}
        </div>
      );
    }

    if (msg.role === 'assistant') {
      /* Render tool calls as indicators */
      const toolCalls = msg.tool_calls?.map((tc) => {
        let argPreview = '';
        try {
          const args = JSON.parse(tc.function.arguments);
          argPreview = ` (${Object.keys(args).length} params)`;
        } catch {
          argPreview = '';
        }
        return (
          <div key={tc.id} style={{ marginTop: 4, fontSize: 10, opacity: 0.6 }}>
            ⚙ {tc.function.name}{argPreview}
          </div>
        );
      });

      return (
        <div key={idx} className="oschertator-msg assistant">
          {content}
          {toolCalls}
        </div>
      );
    }

    return null;
  };

  return (
    <div className="oschertator-widget">
      {open && (
        <div className="oschertator-panel">
          <div className="oschertator-header">
            <span>OSCHERTATOR</span>
            <span className="oschertator-clear" onClick={handleClear}>
              CLEAR
            </span>
          </div>
          <div className="oschertator-messages">
            {messages.length === 0 && !typing && (
              <div style={{ color: 'var(--vault-muted)', fontSize: 11, fontStyle: 'italic', padding: '12px 0' }}>
                Ask me anything about your vault...
              </div>
            )}
            {messages.map(renderMessage)}
            {typing && (
              <div className="oschertator-msg typing">thinking...</div>
            )}
            <div ref={messagesEndRef} />
          </div>
          <div className="oschertator-input-row">
            <input
              ref={inputRef}
              className="oschertator-input"
              type="text"
              placeholder="Message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={typing}
            />
            <button
              className="oschertator-send"
              onClick={() => void handleSend()}
              disabled={typing || !input.trim()}
            >
              {'→'}
            </button>
          </div>
        </div>
      )}
      <button
        className="oschertator-fab"
        onClick={toggleOpen}
        title="Ask Oschertator"
      >
        O
      </button>
    </div>
  );
};

export default OschertatorWidget;
