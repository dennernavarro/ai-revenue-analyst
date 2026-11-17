import { useEffect, useMemo, useState } from 'react';
import { api, monthRange } from './api.js';
import CalendarCard, { needsAttention } from './components/CalendarCard.jsx';
import ChatPanel from './components/ChatPanel.jsx';
import DayCard from './components/DayCard.jsx';
import MonthSummary from './components/MonthSummary.jsx';
import RoomTypesCard from './components/RoomTypesCard.jsx';

const ChatIcon = () => (
  <svg width="18" height="18" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" aria-hidden="true">
    <path d="M4 4h12a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H9l-4 3v-3H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
  </svg>
);

const Chevron = ({ dir }) => (
  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d={dir === 'left' ? 'M10 3L5 8l5 5' : 'M6 3l5 5-5 5'} />
  </svg>
);

const unitWord = (n) => (n === 1 ? 'unit' : 'units');

export default function App() {
  const [properties, setProperties] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [monthOffset, setMonthOffset] = useState(1); // months after "as of"
  const [calendar, setCalendar] = useState([]);
  const [events, setEvents] = useState([]);
  const [benchmark, setBenchmark] = useState(null);
  const [seasons, setSeasons] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [pickedDay, setPickedDay] = useState(null);
  const [chatOpen, setChatOpen] = useState(true);
  const [prefill, setPrefill] = useState(null);
  const [error, setError] = useState(null);
  const [reviewTick, setReviewTick] = useState(0);
  const [dataTick, setDataTick] = useState(0);
  const [previewDays, setPreviewDays] = useState([]);

  const selected = properties.find((p) => p.property_id === selectedId);
  const asOf = selected ? new Date(selected.as_of) : null;

  const view = useMemo(() => {
    if (!asOf) return null;
    const y = asOf.getUTCFullYear();
    const m = asOf.getUTCMonth();
    const first = new Date(Date.UTC(y, m + monthOffset, 1));
    return {
      month: monthRange(y, m + monthOffset),
      monthIndex: first.getUTCMonth(),
      monthName: first.toLocaleDateString('en-US', { month: 'long', timeZone: 'UTC' }),
      monthLabel: first.toLocaleDateString('en-US', { month: 'long', year: 'numeric', timeZone: 'UTC' }),
      realized: monthRange(y, m - 1),
      realizedLabel: new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', {
        month: 'long',
        timeZone: 'UTC',
      }),
    };
  }, [selected, monthOffset]);

  useEffect(() => {
    api.properties().then((list) => {
      setProperties(list);
      setSelectedId(list[0]?.property_id);
    }, setError);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    api.seasons(selectedId).then(setSeasons, setError);
  }, [selectedId]);

  useEffect(() => {
    if (!selected || !view) return;
    setError(null);
    const { start, end } = view.month;
    Promise.all([
      api.calendar(selectedId, start, end),
      api.events(selectedId, start, end),
      api.benchmark(selectedId, start, end),
      api.roomTypes(selectedId, start, end),
      api.performance(selectedId, view.realized.start, view.realized.end),
    ]).then(([days, evs, bench, types, perf]) => {
      setCalendar(days);
      setEvents(evs);
      setBenchmark(bench);
      setRoomTypes(types);
      setPerformance(perf);
      // Open on the first night that needs attention, else the first day.
      setPickedDay((prev) =>
        days.some((d) => d.day === prev) ? prev : (days.find(needsAttention) ?? days[0])?.day,
      );
    }, setError);
  }, [selectedId, monthOffset, properties, dataTick]);

  if (error) {
    return (
      <div className="error-screen">
        <h1>Could not reach the API</h1>
        <p>{String(error.message || error)}</p>
      </div>
    );
  }

  const day = calendar.find((d) => d.day === pickedDay);
  const changeMonth = (delta) => {
    setMonthOffset((v) => v + delta);
    setPreviewDays([]);
    setPickedDay(null);
  };

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 21l5.5-6.5 4.5 3.5 6-8" />
            </svg>
          </span>
          AI Revenue Analyst
        </div>
        <div className="spacer" />
        {asOf && <span className="muted-text small">Data as of {asOf.toISOString().slice(0, 10)}</span>}
        <button type="button" className="btn-outline" onClick={() => setReviewTick((t) => t + 1)}>
          Run pricing review
        </button>
        <button
          type="button"
          className={chatOpen ? 'btn-toggle on' : 'btn-toggle'}
          aria-pressed={chatOpen}
          onClick={() => setChatOpen((v) => !v)}
        >
          <ChatIcon /> Chat
        </button>
      </header>

      <main className="content">
        <div className="controls">
          <nav className="segmented" aria-label="Properties">
            {properties.map((p) => (
              <button
                type="button"
                key={p.property_id}
                aria-pressed={p.property_id === selectedId}
                className={p.property_id === selectedId ? 'seg on' : 'seg'}
                onClick={() => {
                  setSelectedId(p.property_id);
                  setPreviewDays([]);
                  setPickedDay(null);
                  setPrefill(null); // the chat remounts per property; don't refill it
                }}
              >
                {p.name}
              </button>
            ))}
          </nav>
          <div className="month-nav">
            <button type="button" className="icon-btn" aria-label="Previous month" onClick={() => changeMonth(-1)}>
              <Chevron dir="left" />
            </button>
            <h1 className="month-title">{view?.monthLabel}</h1>
            <button type="button" className="icon-btn" aria-label="Next month" onClick={() => changeMonth(1)}>
              <Chevron dir="right" />
            </button>
          </div>
        </div>

        {view && (
          <MonthSummary
            monthName={view.monthName}
            monthIndex={view.monthIndex}
            seasons={seasons}
            benchmark={benchmark}
            performance={performance}
            realizedLabel={view.realizedLabel}
          />
        )}

        <div className="workspace">
          <div className="cal-col">
            <CalendarCard
              days={calendar}
              events={events}
              previewDays={previewDays}
              selected={pickedDay}
              onSelect={setPickedDay}
            />
            {roomTypes.length > 1 && (
              <RoomTypesCard roomTypes={roomTypes} monthLabel={view?.monthLabel} />
            )}
          </div>

          <DayCard
            day={day}
            days={calendar}
            events={events}
            season={view ? seasons[view.monthIndex] : null}
            unitLabel={unitWord}
            onAsk={(d) => {
              const label = new Date(`${d.day}T00:00:00Z`).toLocaleDateString('en-US', {
                weekday: 'short',
                month: 'short',
                day: 'numeric',
                timeZone: 'UTC',
              });
              setChatOpen(true);
              setPrefill({ text: `What's going on with ${label}?`, at: Date.now() });
            }}
          />

          {selected && view && (
            <ChatPanel
              key={selectedId}
              hidden={!chatOpen}
              propertyId={selectedId}
              propertyName={selected.name}
              month={view.month}
              monthLabel={view.monthLabel}
              reviewTick={reviewTick}
              prefill={prefill}
              onClose={() => setChatOpen(false)}
              onOpen={() => setChatOpen(true)}
              onRatesPublished={() => setDataTick((t) => t + 1)}
              onPreviewDays={setPreviewDays}
            />
          )}
        </div>
      </main>
    </div>
  );
}
