import { useRef, useState } from 'react';
import { api } from '../api.js';

const SUGGESTIONS = ['Compare with last month', 'Show weekend rates', 'Why is pace low?'];

export default function ChatPanel({ propertyId, propertyName, month, monthLabel }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const conversationId = useRef(null);
  const append = (msg) => setMessages((prev) => [...prev, msg]);

  async function send(text) {
    const question = text.trim();
    if (!question || busy) return;
    setInput('');
    setBusy(true);
    append({ kind: 'user', text: question });
    try {
      const res = await api.chat(question, conversationId.current);
      conversationId.current = res.conversation_id;
      if (res.tool_calls.length) append({ kind: 'tools', calls: res.tool_calls });
      append({ kind: 'assistant', text: res.reply });
    } catch (err) {
      append({ kind: 'assistant', text: `Something went wrong: ${err.message}` });
    } finally {
      setBusy(false);
    }
  }

  async function startReview() {
    if (busy) return;
    setBusy(true);
    append({ kind: 'user', text: `Run a pricing review for ${monthLabel}.` });
    try {
      const res = await api.startReview(propertyId, month.start, month.end);
      if (res.status === 'pending_approval') {
        append({ kind: 'review', review: res, monthLabel, resolved: false });
      } else {
        append({ kind: 'assistant', text: res.outcome });
      }
    } catch (err) {
      append({ kind: 'assistant', text: `Review failed: ${err.message}` });
    } finally {
      setBusy(false);
    }
  }

  async function decide(index, reviewId, approved) {
    setBusy(true);
    try {
      const res = await api.decideReview(reviewId, approved);
      setMessages((prev) =>
        prev.map((m, i) => (i === index ? { ...m, resolved: true, approved } : m)),
      );
      append({ kind: 'assistant', text: res.outcome });
    } catch (err) {
      append({ kind: 'assistant', text: `Decision failed: ${err.message}` });
    } finally {
      setBusy(false);
    }
  }

  return (
    <aside className="chat">
      <div className="chat-head">
        <div>
          <div className="chat-title">Revenue analyst</div>
          <div className="chat-sub">every number comes from tools</div>
        </div>
        <button className="btn-outline" onClick={startReview} disabled={busy}>
          Run pricing review
        </button>
      </div>

      <div className="chat-scroll">
        {messages.length === 0 && (
          <div className="chat-empty">
            Ask about {propertyName}&apos;s performance, booking pace or rates — or run a pricing
            review for {monthLabel}.
          </div>
        )}
        {messages.map((m, i) => {
          if (m.kind === 'user') {
            return (
              <div key={i} className="bubble user">
                {m.text}
              </div>
            );
          }
          if (m.kind === 'tools') {
            return (
              <div key={i} className="tool-chips">
                {m.calls.map((c, j) => (
                  <span key={j} className="tool-chip">
                    ⚙ {c.name}({Object.values(c.args).join(', ')})
                  </span>
                ))}
              </div>
            );
          }
          if (m.kind === 'review') {
            return (
              <div key={i} className="review-card">
                <div className="review-tag">
                  {m.resolved ? (m.approved ? 'APPROVED' : 'DECLINED') : 'PENDING APPROVAL'}
                </div>
                <div className="review-title">
                  {m.review.proposal.adjustment_pct > 0 ? '+' : ''}
                  {m.review.proposal.adjustment_pct}% on published rates
                </div>
                <p className="review-body">{m.review.proposal.rationale}</p>
                <p className="review-body muted-text">{m.review.proposal.expected_effect}</p>
                {!m.resolved && (
                  <div className="review-actions">
                    <button
                      className="btn-primary"
                      disabled={busy}
                      onClick={() => decide(i, m.review.review_id, true)}
                    >
                      Approve
                    </button>
                    <button
                      className="btn-outline"
                      disabled={busy}
                      onClick={() => decide(i, m.review.review_id, false)}
                    >
                      Decline
                    </button>
                  </div>
                )}
              </div>
            );
          }
          return (
            <div key={i} className="bubble assistant">
              {m.text}
            </div>
          );
        })}
        {busy && <div className="bubble assistant thinking">Working…</div>}
      </div>

      <div className="chat-suggestions">
        {SUGGESTIONS.map((s) => (
          <button key={s} className="chip" onClick={() => send(s)} disabled={busy}>
            {s}
          </button>
        ))}
      </div>
      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
      >
        <label htmlFor="chat-box" className="sr-only">
          Ask the analyst
        </label>
        <input
          id="chat-box"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about performance, pace, rates…"
          autoComplete="off"
        />
        <button type="submit" className="btn-primary send" aria-label="Send message" disabled={busy}>
          ➤
        </button>
      </form>
    </aside>
  );
}
