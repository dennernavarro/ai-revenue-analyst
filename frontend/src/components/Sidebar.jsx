const NAV = ['Overview', 'Calendar', 'Rooms & rates', 'Pricing reviews', 'Reports'];

export default function Sidebar({ properties, selectedId, onSelect }) {
  return (
    <nav className="sidebar">
      {NAV.map((item, i) => (
        <a
          key={item}
          href={`#${item.toLowerCase().replace(/[^a-z]+/g, '-')}`}
          className={i === 0 ? 'nav-link active' : 'nav-link'}
          aria-current={i === 0 ? 'page' : undefined}
        >
          {item}
        </a>
      ))}
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
