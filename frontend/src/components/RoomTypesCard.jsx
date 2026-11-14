export default function RoomTypesCard({ roomTypes, monthLabel }) {
  return (
    <section className="card">
      <div className="card-head">
        <h2>Room categories</h2>
        <span className="card-sub">{monthLabel} occupancy</span>
      </div>
      <div className="rt-grid rt-head">
        <div>CATEGORY</div>
        <div>UNITS</div>
        <div>FROM</div>
        <div>SOLD</div>
        <div />
      </div>
      {roomTypes.map((rt) => (
        <div className="rt-grid rt-row" key={rt.room_type_id}>
          <div className="rt-name">{rt.name}</div>
          <div className="muted-text">{rt.units}</div>
          <div>${rt.from_rate}</div>
          <div className="rt-bar">
            <div className="rt-bar-fill" style={{ width: `${Math.round(rt.occupancy * 100)}%` }} />
          </div>
          <div className="rt-pct">{Math.round(rt.occupancy * 100)}%</div>
        </div>
      ))}
    </section>
  );
}
