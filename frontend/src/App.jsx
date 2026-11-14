import { useEffect, useMemo, useState } from 'react';
import { api, monthRange } from './api.js';
import CalendarCard from './components/CalendarCard.jsx';
import ChatPanel from './components/ChatPanel.jsx';
import KpiRow from './components/KpiRow.jsx';
import RoomTypesCard from './components/RoomTypesCard.jsx';
import Sidebar from './components/Sidebar.jsx';

export default function App() {
  const [properties, setProperties] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [monthOffset, setMonthOffset] = useState(1); // months after "as of"
  const [calendar, setCalendar] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [error, setError] = useState(null);

  const selected = properties.find((p) => p.property_id === selectedId);
  const asOf = selected ? new Date(selected.as_of) : null;

  const view = useMemo(() => {
    if (!asOf) return null;
    const y = asOf.getUTCFullYear();
    const m = asOf.getUTCMonth();
    return {
      month: monthRange(y, m + monthOffset),
      monthLabel: new Date(Date.UTC(y, m + monthOffset, 1)).toLocaleDateString('en-US', {
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC',
      }),
      realized: monthRange(y, m - 1),
      realizedLabel: new Date(Date.UTC(y, m - 1, 1)).toLocaleDateString('en-US', {
        month: 'short',
        timeZone: 'UTC',
      }),
    };
  }, [selected, monthOffset]);

  useEffect(() => {
    api.properties().then((list) => {
      setProperties(list);
      setSelectedId(list[1]?.property_id ?? list[0]?.property_id);
    }, setError);
  }, []);

  useEffect(() => {
    if (!selected || !view) return;
    setError(null);
    Promise.all([
      api.calendar(selectedId, view.month.start, view.month.end),
      api.roomTypes(selectedId, view.month.start, view.month.end),
      api.performance(selectedId, view.realized.start, view.realized.end),
    ]).then(([days, types, perf]) => {
      setCalendar(days);
      setRoomTypes(types);
      setPerformance(perf);
    }, setError);
  }, [selectedId, monthOffset, properties]);

  if (error) {
    return (
      <div className="error-screen">
        <h1>Could not reach the API</h1>
        <p>{String(error.message || error)}</p>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            ✦
          </span>
          AI Revenue Analyst
        </div>
        {selected && (
          <span className="pill">
            {selected.name} · {selected.city}
          </span>
        )}
        <div className="spacer" />
        {asOf && <span className="pill muted">Data as of {asOf.toISOString().slice(0, 10)}</span>}
      </header>

      <div className="layout">
        <Sidebar
          properties={properties}
          selectedId={selectedId}
          onSelect={(id) => setSelectedId(id)}
        />

        <main className="content">
          <KpiRow
            performance={performance}
            realizedLabel={view?.realizedLabel}
            calendar={calendar}
            monthLabel={view?.monthLabel}
          />
          <CalendarCard
            days={calendar}
            monthLabel={view?.monthLabel}
            onPrev={() => setMonthOffset((v) => v - 1)}
            onNext={() => setMonthOffset((v) => v + 1)}
          />
          <RoomTypesCard roomTypes={roomTypes} monthLabel={view?.monthLabel} />
        </main>

        {selected && view && (
          <ChatPanel
            key={selectedId}
            propertyId={selectedId}
            propertyName={selected.name}
            month={view.month}
            monthLabel={view.monthLabel}
          />
        )}
      </div>
    </div>
  );
}
