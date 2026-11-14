const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

export default function CalendarCard({ days, previewDays = [], monthLabel, onPrev, onNext }) {
  const preview = new Set(previewDays);
  const blanks = days.length ? new Date(`${days[0].day}T00:00:00Z`).getUTCDay() : 0;

  return (
    <section className="card">
      <div className="card-head">
        <h2>{monthLabel}</h2>
        <span className="card-sub">nightly rate · nights sold per day</span>
        <div className="spacer" />
        <div className="legend">
          low
          <span className="swatch s1" aria-hidden="true" />
          <span className="swatch s2" aria-hidden="true" />
          <span className="swatch s3" aria-hidden="true" />
          sold
        </div>
        <button className="icon-btn" aria-label="Previous month" onClick={onPrev}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M15 6l-6 6 6 6" />
          </svg>
        </button>
        <button className="icon-btn" aria-label="Next month" onClick={onNext}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 6l6 6-6 6" />
          </svg>
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
          const alpha = share === 0 ? 0 : 0.11 + share * 0.43;
          const classes = ['cal-cell'];
          if (share) classes.push('filled');
          if (preview.has(d.day)) classes.push('preview');
          return (
            <div
              key={d.day}
              className={classes.join(' ')}
              style={share ? { background: `rgba(14, 107, 83, ${alpha})` } : undefined}
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
