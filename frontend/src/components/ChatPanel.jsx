import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, chatStream } from '../api.js';

const SUGGESTIONS = ['Compare with last month', 'Show weekend rates', 'Why is pace low?'];

const GearIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.2 2.2M16.9 16.9l2.2 2.2M19.1 4.9l-2.2 2.2M7.1 16.9l-2.2 2.2" />
  </svg>
);

export default function ChatPanel({
  propertyId,
  propertyName,
  month,
  monthLabel,
  reviewTick,
  onRatesPublished,
  onPreviewDays,
}) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const conversationId = useRef(null);
  const scrollRef = useRef(null);
  const append = (msg) => setMessages((prev) => [...prev, msg]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, busy]);

  async function send(text) {
    const question = text.trim();
    if (!question || busy) return;
    setInput('');
    setBusy(true);
    append({ kind: 'user', text: question });
    try {
      const view = { propertyId, monthStart: month.start, monthEnd: month.end };
      await chatStream(question, conversationId.current, view, (event) => {
        if (event.type === 'start') {
          conversationId.current = event.conversation_id;
        } else if (event.type === 'tool') {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.kind === 'tools') {
              next[next.length - 1] = { ...last, calls: [...last.calls, event] };
            } else {
              next.push({ kind: 'tools', calls: [event] });
            }
            return next;
          });
        } else if (event.type === 'token') {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last?.kind === 'assistant' && last.streaming) {
              next[next.length - 1] = { ...last, text: last.text + event.text };
            } else {
              next.push({ kind: 'assistant', streaming: true, text: event.text });
            }
            return next;
          });
        } else if (event.type === 'done') {
          setMessages((prev) => prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)));
        }
      });
    } catch (err) {
      append({ kind: 'assistant', text: `Something went wrong: ${err.message}` });
    } finally {
      setBusy(false);
    }
  }

  const reviewInFlight = useRef(false);

  async function startReview() {
    if (busy || reviewInFlight.current) return;
    reviewInFlight.current = true;
    setBusy(true);
    append({ kind: 'user', text: `Run a pricing review for ${monthLabel}.` });
    try {
      const res = await api.startReview(propertyId, month.start, month.end);
      if (res.status === 'pending_approval') {
        append({ kind: 'review', review: res, resolved: false });
        onPreviewDays?.(res.target_days ?? []);
      } else {
        append({ kind: 'assistant', text: res.outcome });
      }
    } catch (err) {
      append({ kind: 'assistant', text: `Review failed: ${err.message}` });
    } finally {
      reviewInFlight.current = false;
      setBusy(false);
    }
  }

  const lastTick = useRef(reviewTick);
  useEffect(() => {
    if (reviewTick !== lastTick.current) {
      lastTick.current = reviewTick;
      startReview();
    }
  }, [reviewTick]);

  async function decide(index, reviewId, approved) {
    setBusy(true);
    try {
      const res = await api.decideReview(reviewId, approved);
      setMessages((prev) =>
        prev.map((m, i) => (i === index ? { ...m, resolved: true, approved } : m)),
      );
      append({ kind: 'assistant', text: res.outcome });
      onPreviewDays?.([]);
      if (approved && res.outcome.includes('PUBLISHED')) onRatesPublished?.();
    } catch (err) {
      append({ kind: 'assistant', text: `Decision failed: ${err.message}` });
    } finally {
      setBusy(false);
    }
  }

  const streamingNow = messages.some((m) => m.streaming);

  return (
    <aside className="chat">
      <div className="chat-head">
        <div className="chat-mark" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
          </svg>
        </div>
        <div>
          <div className="chat-title">Revenue analyst</div>
          <div className="chat-sub">every number comes from tools</div>
        </div>
      </div>

      <div className="chat-scroll" ref={scrollRef}>
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
                    <GearIcon /> {c.name}({Object.values(c.args).join(', ')})
                  </span>
                ))}
              </div>
            );
          }
          if (m.kind === 'review') {
            return (
              <div key={i} className="review-card">
                <div className="review-row">
                  <span className="review-tag">
                    {m.resolved ? (m.approved ? 'APPROVED' : 'DECLINED') : 'PENDING APPROVAL'}
                  </span>
                  <span className="review-when">Pricing review · {monthLabel}</span>
                </div>
                <div className="review-title">
                  {m.review.proposal.adjustment_pct > 0 ? '+' : ''}
                  {m.review.proposal.adjustment_pct}% on published rates
                </div>
                {m.review.target_days?.length > 0 && (
                  <p className="review-body targets">
                    Applies to {m.review.target_days.length} slow-pacing dates — highlighted on
                    the calendar. Well-selling dates keep their price.
                  </p>
                )}
                <p className="review-body">{m.review.proposal.rationale}</p>
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
                      className="btn-outline grow"
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
            <div key={i} className="bubble assistant md">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
              {m.streaming && <span className="caret" aria-hidden="true" />}
            </div>
          );
        })}
        {busy && !streamingNow && <div className="bubble assistant thinking">Working…</div>}
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
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4z" />
          </svg>
        </button>
      </form>
    </aside>
  );
}
