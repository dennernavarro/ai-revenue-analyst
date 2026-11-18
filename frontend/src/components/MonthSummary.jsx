const LEVEL = { peak: 'peak season', high: 'a busy month', shoulder: 'shoulder season', low: 'low season' };
const pct = (v) => `${Math.round(v * 100)}%`;
const usd = (v) => `$${Math.round(v).toLocaleString('en-US')}`;

function Pace({ benchmark }) {
  if (!benchmark) return null;
  const now = pct(benchmark.on_the_books_share);
  if (benchmark.basis === 'fixed_threshold') {
    return <>{now} booked so far (no last-year data to compare with).</>;
  }
  const ly = pct(benchmark.last_year_share_same_lead_time);
  return benchmark.behind ? (
    <>
      <span className="behind-text">you're behind</span>: {now} booked vs {ly} last year by now.
    </>
  ) : (
    <>
      <span className="accent-text">you're on track</span>: {now} booked vs {ly} last year by now.
    </>
  );
}

export default function MonthSummary({ monthName, monthIndex, seasons, benchmark, performance, realizedLabel }) {
  const season = seasons[monthIndex];
  const max = Math.max(...seasons.map((s) => s.index), 1);
  return (
    <section className="summary" aria-label="Month summary">
      <div className="summary-text">
        <p className="summary-line">
          {monthName} is {season ? LEVEL[season.level] : 'loading'}, and <Pace benchmark={benchmark} />
        </p>
        {benchmark?.aligned_on && benchmark.shift_days !== 364 && (
          <p className="small muted-text">
            Compared with last year's {benchmark.aligned_on}, not the same dates.
          </p>
        )}
        {performance && (
          <p className="small muted-text">
            {realizedLabel}: {pct(performance.occupancy)} occupied · {usd(performance.adr)} ADR ·{' '}
            {usd(performance.revpar)} RevPAR
          </p>
        )}
      </div>
      <figure className="season-bars" aria-label="How busy each month was last year">
        <div className="bars">
          {seasons.map((s, i) => (
            <div key={s.month} className="bar-col">
              <span
                className={i === monthIndex ? 'bar current' : 'bar'}
                style={{ height: `${Math.max(6, Math.round((s.index / max) * 36))}px` }}
                title={`${s.level} · ×${s.index}`}
              />
              <span className={i === monthIndex ? 'bar-label current' : 'bar-label'}>
                {'JFMAMJJASOND'[i]}
              </span>
            </div>
          ))}
        </div>
        <figcaption className="small muted-text">Last year, by month</figcaption>
      </figure>
    </section>
  );
}
