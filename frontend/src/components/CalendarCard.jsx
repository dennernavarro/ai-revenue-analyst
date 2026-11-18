const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// Five steps from empty to sold out; the cell shows only date, price, how
// full (shade) and two exception markers — the day card holds the rest.
export function fillStep(day) {
  if (!day.capacity || !day.nights_sold) return 0;
  if (day.nights_sold >= day.capacity) return 4;
  return Math.min(3, 1 + Math.floor((day.nights_sold / day.capacity) * 3));
}

export const needsAttention = (day) => day.status === 'behind' || day.arrival_blocked;

export function eventsOn(events, iso) {
  return events.filter((e) => e.start <= iso && iso < e.end);
}

const fmtDay = (iso) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  });

export default function CalendarCard({ days, events, previewDays = [], selected, onSelect }) {
  const preview = new Set(previewDays);
  const blanks = days.length ? new Date(`${days[0].day}T00:00:00Z`).getUTCDay() : 0;

  return (
    <section className="calendar" aria-label="Calendar">
      <div className="cal-grid cal-head" aria-hidden="true">
        {WEEKDAYS.map((w) => (
          <div key={w}>{w}</div>
        ))}
      </div>
      <div className="cal-grid">
        {Array.from({ length: blanks }, (_, i) => (
          <div key={`b${i}`} />
        ))}
        {days.map((d) => {
          const step = fillStep(d);
          const event = eventsOn(events, d.day)[0];
          const flag = needsAttention(d);
          const classes = ['cal-cell', `fill-${step}`];
          if (d.day === selected) classes.push('selected');
          if (preview.has(d.day)) classes.push('preview');
          const label = [
            fmtDay(d.day),
            `$${d.rate}`,
            step === 4 ? 'sold out' : `${d.nights_sold} of ${d.capacity} booked`,
            flag ? (d.arrival_blocked ? 'nobody can check in' : 'behind similar nights last year') : null,
            event ? event.name : null,
          ]
            .filter(Boolean)
            .join(', ');
          return (
            <button
              type="button"
              key={d.day}
              className={classes.join(' ')}
              aria-pressed={d.day === selected}
              aria-label={label}
              onClick={() => onSelect(d.day)}
            >
              {event && <span className="cal-event" aria-hidden="true" />}
              <span className="cal-top">
                <span className="cal-day">{Number(d.day.slice(8))}</span>
                {flag && <span className="cal-flag" aria-hidden="true" />}
              </span>
              <span className="cal-rate">${Math.round(d.rate)}</span>
            </button>
          );
        })}
      </div>
      <div className="cal-legend">
        <span className="legend-item">
          <span className="swatch fill-0" aria-hidden="true" />
          <span className="swatch fill-2" aria-hidden="true" />
          <span className="swatch fill-3" aria-hidden="true" />
          <span className="swatch fill-4" aria-hidden="true" />
          darker = more booked
        </span>
        <span className="legend-item">
          <span className="legend-event" aria-hidden="true" />
          holiday or event
        </span>
        <span className="legend-item">
          <span className="legend-flag" aria-hidden="true" />
          behind similar nights last year
        </span>
        <span>Click a day for the full story.</span>
      </div>
    </section>
  );
}
