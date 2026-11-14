const pct = (v) => `${(v * 100).toFixed(1)}%`;
const usd = (v) => `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function KpiRow({ performance, realizedLabel, calendar, monthLabel }) {
  const sold = calendar.reduce((acc, d) => acc + d.nights_sold, 0);
  const capacity = calendar.reduce((acc, d) => acc + d.capacity, 0);
  const share = capacity ? sold / capacity : 0;

  return (
    <div className="kpi-row">
      <div className="card kpi">
        <div className="kpi-label">Occupancy · {realizedLabel} realized</div>
        <div className="kpi-value">{performance ? pct(performance.occupancy) : '—'}</div>
        <div className="kpi-sub">
          {performance ? `${performance.nights_sold} of ${performance.nights_available} nights` : ''}
        </div>
      </div>
      <div className="card kpi">
        <div className="kpi-label">ADR · {realizedLabel} realized</div>
        <div className="kpi-value">{performance ? usd(performance.adr) : '—'}</div>
        <div className="kpi-sub">avg daily rate</div>
      </div>
      <div className="card kpi">
        <div className="kpi-label">RevPAR · {realizedLabel} realized</div>
        <div className="kpi-value">{performance ? usd(performance.revpar) : '—'}</div>
        <div className="kpi-sub">revenue per available night</div>
      </div>
      <div className="card kpi">
        <div className="kpi-label">{monthLabel} on the books</div>
        <div className={share < 0.3 ? 'kpi-value warn' : 'kpi-value'}>{pct(share)}</div>
        <div className="kpi-sub">
          {sold} of {capacity} nights
        </div>
      </div>
    </div>
  );
}
