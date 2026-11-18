import { eventsOn } from './CalendarCard.jsx';

const LEVEL = { peak: 'Peak', high: 'High', shoulder: 'Shoulder', low: 'Low' };
const KIND = { event: 'holiday', weekend: 'weekend', weekday: 'weekday' };

const utc = (iso) => new Date(`${iso}T00:00:00Z`);
const fmt = (date, opts) => date.toLocaleDateString('en-US', { ...opts, timeZone: 'UTC' });
const addDays = (iso, n) => new Date(utc(iso).getTime() + n * 86400000);
const one = (x) => (Number.isInteger(x) ? String(x) : x.toFixed(1));

function insightFor(day, days) {
  const peer = day.peer_booked;
  if (day.status === 'sold_out') return { tone: 'good', text: 'Sold out. Nothing to do here.' };
  if (day.arrival_blocked) {
    const i = days.findIndex((d) => d.day === day.day);
    const full = days.slice(i + 1, i + day.min_stay).find((d) => d.status === 'sold_out');
    const why = full ? `${fmt(utc(full.day), { month: 'short', day: 'numeric' })} is sold out` : 'the following night is sold out';
    return {
      tone: 'behind',
      text: `Nobody can check in tonight: arrivals need ${day.min_stay} nights, and ${why}.`,
    };
  }
  const vs = peer == null ? '' : ` vs ${one(peer)} on similar nights last year by now`;
  switch (day.status) {
    case 'behind':
      return { tone: 'behind', text: `You're behind: ${day.nights_sold} booked${vs}.` };
    case 'on_track':
      return { tone: 'ahead', text: `On track: ${day.nights_sold} booked${vs}.` };
    case 'too_early':
      return {
        tone: 'neutral',
        text: 'Too early to tell: similar nights last year had little booked by now too.',
      };
    default:
      return { tone: 'neutral', text: 'No last-year data to compare with yet.' };
  }
}

function eventLine(event) {
  // end is exclusive: the last night is the day before
  const short = { month: 'short', day: 'numeric' };
  const range = `${fmt(utc(event.start), short)} to ${fmt(addDays(event.end, -1), short)}`;
  const x = event.impact;
  const effect =
    x >= 1.9 ? 'Demand here usually doubles' : x > 1 ? `Demand here is usually ×${x}` : `Usually quieter here (×${x})`;
  return `${range}. ${effect}${x > 1 ? ', and guests book earlier' : ''}.`;
}

export default function DayCard({ day, days, events, season, unitLabel, onAsk }) {
  if (!day) return <aside className="day-card empty">Pick a day to see the details.</aside>;
  const date = utc(day.day);
  const insight = insightFor(day, days);
  const dayEvents = eventsOn(events, day.day);
  const lyDate = fmt(addDays(day.day, -364), { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' });

  return (
    <aside className="day-card" aria-label="Selected night">
      <div>
        <div className="muted-text">{fmt(date, { weekday: 'long' })}</div>
        <h2 className="day-title">{fmt(date, { month: 'long', day: 'numeric' })}</h2>
      </div>

      <div className={`insight ${insight.tone}`}>{insight.text}</div>

      <div className="day-price">
        <span className="price">${Math.round(day.rate)}</span>
        <span className="muted-text">
          {day.min_stay > 1 ? `${day.min_stay}-night minimum` : 'No minimum stay'}
        </span>
      </div>

      <div>
        {day.capacity <= 12 && (
          <div className="unit-dots" aria-hidden="true">
            {Array.from({ length: day.capacity }, (_, k) => (
              <span key={k} className={k < day.nights_sold ? 'dot on' : 'dot'} />
            ))}
          </div>
        )}
        <div className="day-booked">
          {day.nights_sold >= day.capacity
            ? `All ${day.capacity} ${unitLabel(day.capacity)} booked`
            : `${day.nights_sold} of ${day.capacity} ${unitLabel(day.capacity)} booked`}
        </div>
      </div>

      <dl className="day-facts">
        <dt>Similar nights last year, by now</dt>
        <dd>{day.peer_booked == null ? '—' : `${one(day.peer_booked)} of ${day.capacity}`}</dd>
        <dt>Same night last year, final</dt>
        <dd>
          {day.last_year_final} of {day.capacity}
        </dd>
        <dt>Season</dt>
        <dd>{season ? `${LEVEL[season.level]} · ×${season.index}` : '—'}</dd>
      </dl>

      {dayEvents.map((e) => (
        <div className="event-note" key={`${e.name}-${e.start}`}>
          <span className="event-bar" aria-hidden="true" />
          <div>
            <div className="strong">{e.name}</div>
            <div className="small">{eventLine(e)}</div>
          </div>
        </div>
      ))}

      <p className="small muted-text">
        Similar nights: last year's {KIND[day.kind]} nights within a week of {lyDate}, same
        days before arrival. Season: last year's occupancy for this month vs an average month.
      </p>

      <button type="button" className="btn-outline" onClick={() => onAsk(day)}>
        Ask about this night
      </button>
    </aside>
  );
}
