const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function CalendarCard({ days, monthLabel, onPrev, onNext }) {
  const blanks = days.length ? new Date(`${days[0].day}T00:00:00Z`).getUTCDay() : 0;

  return (
    <section className="card">
      <div className="card-head">
        <h2>{monthLabel}</h2>
        <span className="card-sub">nightly rate · nights sold per day</span>
        <div className="spacer" />
        <button className="icon-btn" aria-label="Previous month" onClick={onPrev}>
          ‹
        </button>
        <button className="icon-btn" aria-label="Next month" onClick={onNext}>
          ›
        </button>
      </div>
      <div className="cal-grid cal-head">
        {WEEKDAYS.map((w) => (
          <div key={w}>{w}</div>
        ))}
      </div>
      <div className="cal-grid">
        {Array.from({ length: blanks }, (_, i) => (
          <div key={`b${i}`} />
        ))}
        {days.map((d) => {
          const share = d.capacity ? d.nights_sold / d.capacity : 0;
          const alpha = share === 0 ? 0 : 0.1 + share * 0.45;
          return (
            <div
              key={d.day}
              className="cal-cell"
              style={{ background: alpha ? `rgba(14, 107, 83, ${alpha})` : '#fff' }}
              title={`${d.day}: ${d.nights_sold}/${d.capacity} sold at $${d.rate}`}
            >
              <div className="cal-top">
                <span className="cal-day">{Number(d.day.slice(8))}</span>
                <span className="cal-rate">${d.rate}</span>
              </div>
              <div className="cal-sold">
                {d.nights_sold}/{d.capacity}
                {d.min_stay > 1 ? ` · min ${d.min_stay}n` : ''}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
