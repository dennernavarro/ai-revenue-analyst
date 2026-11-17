import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, chatStream } from '../api.js';

const SUGGESTIONS = ['Compare with last month', 'Show weekend rates', 'Why is pace low?'];

// Deep mode shines on portfolio-sized, multi-step missions — the chips
// should invite exactly those, not single-tool questions.
const DEEP_SUGGESTIONS = [
  'Review all properties for next quarter',
  'Compare every property with last year',
  'Which property needs pricing action first?',
];

const GearIcon = () => (
  <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.2 2.2M16.9 16.9l2.2 2.2M19.1 4.9l-2.2 2.2M7.1 16.9l-2.2 2.2" />
  </svg>
);

const BranchIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="6" cy="6" r="2.5" />
    <circle cx="6" cy="18" r="2.5" />
    <circle cx="18" cy="12" r="2.5" />
    <path d="M8.5 6H13a3 3 0 0 1 3 3v0M8.5 18H13a3 3 0 0 0 3-3v0" />
  </svg>
);

const SUBAGENT_NAMES = {
  'performance-analyst': 'Performance analyst',
  'pacing-analyst': 'Pacing analyst',
  'general-purpose': 'General assistant',
};

const titleCase = (slug) =>
  String(slug || '')
    .split('-')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');

const fmtDate = (iso) => {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
};

function describeToolCall(call) {
  const a = call.args || {};
  const range =
    a.start_date && a.end_date ? ` · ${fmtDate(a.start_date)} → ${fmtDate(a.end_date)}` : '';
  const prop = a.property_id ? ` — ${titleCase(a.property_id)}` : '';
  switch (call.name) {
    case 'list_properties':
      return { kind: 'chip', label: 'Looking up the property list' };
    case 'get_performance':
      return { kind: 'chip', label: `Analyzing performance${prop}${range}` };
    case 'get_booking_pace':
      return { kind: 'chip', label: `Checking booking pace${prop}${range}` };
    case 'get_rates':
      return { kind: 'chip', label: `Reviewing published rates${prop}${range}` };
    case 'get_events':
      return { kind: 'chip', label: `Checking holidays & events${prop}${range}` };
    case 'task':
      return {
        kind: 'delegate',
        agent: SUBAGENT_NAMES[a.subagent_type] || titleCase(a.subagent_type),
        detail: a.description || '',
      };
    case 'write_todos':
      return { kind: 'plan', todos: Array.isArray(a.todos) ? a.todos : [] };
    case 'write_file':
      return { kind: 'chip', label: `Saving notes${a.file_path ? ` (${a.file_path})` : ''}` };
    case 'read_file':
    case 'ls':
      return { kind: 'chip', label: 'Reading workspace notes' };
    default:
      return { kind: 'chip', label: titleCase(call.name) };
  }
}

function ToolActivity({ call }) {
  const info = describeToolCall(call);
  if (info.kind === 'delegate') {
    return (
      <div className="delegate-card">
        <div className="delegate-head">
          <BranchIcon /> Delegated to <strong>{info.agent}</strong>
        </div>
        {info.detail && <div className="delegate-detail">{info.detail}</div>}
      </div>
    );
  }
  if (info.kind === 'plan') {
    return (
      <div className="plan-card">
        <div className="delegate-head">
          <GearIcon /> Planning
        </div>
        <ul className="plan-list">
          {info.todos.map((todo, i) => (
            <li key={i} className={todo.status === 'completed' ? 'done' : undefined}>
              {todo.content}
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <span className="tool-chip">
      <GearIcon /> {info.label}
    </span>
  );
}

export default function ChatPanel({
  hidden = false,
  prefill,
  onClose,
  onOpen,
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
  const [deepMode, setDeepMode] = useState(false);
  const conversationId = useRef(null);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  // "Ask about this night" fills the box; the user sends it.
  useEffect(() => {
    if (!prefill) return;
    setInput(prefill.text);
    inputRef.current?.focus();
  }, [prefill]);
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
      const view = { propertyId, monthStart: month.start, monthEnd: month.end, deep: deepMode };
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
    onOpen?.();
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
    <aside className={deepMode ? 'chat deep' : 'chat'} hidden={hidden} aria-label="Chat with the analyst">
      <div className="chat-head">
        <div className="chat-mark" aria-hidden="true">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
          </svg>
        </div>
        <div>
          <div className="chat-title">Ask the analyst</div>
          <div className="chat-sub">
            {deepMode ? 'deep: plans and delegates to subagents' : 'every number comes from tools'}
          </div>
        </div>
        <div className="spacer" />
        <button
          className={deepMode ? 'chip deep-toggle on' : 'chip deep-toggle'}
          aria-pressed={deepMode}
          disabled={busy}
          onClick={() => {
            // The deep agent keeps different graph state, so flipping the
            // switch starts a fresh conversation thread.
            setDeepMode((v) => !v);
            conversationId.current = null;
          }}
        >
          Deep
        </button>
        <button type="button" className="icon-btn" aria-label="Close chat" onClick={onClose}>
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <path d="M4 4l8 8M12 4l-8 8" />
          </svg>
        </button>
      </div>

      <div className="chat-scroll" ref={scrollRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            {deepMode
              ? 'Deep mode: give the lead analyst a portfolio-sized mission. It will plan the work, delegate to specialist subagents and synthesize their reports.'
              : `Ask about ${propertyName}'s performance, booking pace or rates — or run a pricing review for ${monthLabel}.`}
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
                  <ToolActivity key={j} call={c} />
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
        {(deepMode ? DEEP_SUGGESTIONS : SUGGESTIONS).map((s) => (
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
          ref={inputRef}
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
