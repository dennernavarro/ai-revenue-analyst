export default function Sidebar({ properties, selectedId, onSelect }) {
  return (
    <nav className="sidebar">
      <div className="sidebar-label">PROPERTIES</div>
      {properties.map((p) => (
        <button
          key={p.property_id}
          className={p.property_id === selectedId ? 'prop-row active' : 'prop-row'}
          onClick={() => onSelect(p.property_id)}
        >
          <span>{p.name}</span>
          <span className="prop-units">
            {p.units} {p.units === 1 ? 'unit' : 'units'}
          </span>
        </button>
      ))}
    </nav>
  );
}
