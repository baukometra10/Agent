"use client";

type BlastItem = {
  category?: string;
  title?: string;
  path?: string | null;
  confidence?: number;
};

type Props = {
  simulation: Record<string, unknown> | null;
};

export function TwinBlastViz({ simulation }: Props) {
  if (!simulation) {
    return <p className="ide-venture__hint">Noch keine Simulation — Twin bauen oder Venture-Phase «simulate» abwarten.</p>;
  }

  const blast = (Array.isArray(simulation.blast_radius) ? simulation.blast_radius : []) as BlastItem[];
  const layers = (Array.isArray(simulation.layers_impacted) ? simulation.layers_impacted : []).map(String);
  const risks = (Array.isArray(simulation.risks) ? simulation.risks : []) as Array<Record<string, unknown>>;
  const score = Number(simulation.risk_score ?? 0);
  const rec = String(simulation.recommendation || "");
  const byCat: Record<string, number> = {};
  for (const b of blast) {
    const c = String(b.category || "other");
    byCat[c] = (byCat[c] || 0) + 1;
  }
  const max = Math.max(1, ...Object.values(byCat), blast.length);

  return (
    <div className="twin-blast">
      <div className="twin-blast__meter">
        <span>Risiko</span>
        <div className="twin-blast__bar">
          <i style={{ width: `${Math.min(100, Math.round(score * 100))}%` }} />
        </div>
        <em>{score.toFixed(2)}</em>
      </div>
      <p className="twin-blast__rec">{rec}</p>
      {layers.length ? (
        <div className="twin-blast__layers">
          {layers.map((l) => (
            <span key={l}>{l}</span>
          ))}
        </div>
      ) : null}
      <div className="twin-blast__cats">
        {Object.entries(byCat).map(([cat, n]) => (
          <div key={cat} className="twin-blast__cat">
            <span>{cat}</span>
            <div>
              <i style={{ width: `${Math.round((n / max) * 100)}%` }} />
            </div>
            <em>{n}</em>
          </div>
        ))}
      </div>
      {risks.length ? (
        <ul className="twin-blast__risks">
          {risks.slice(0, 6).map((r, i) => (
            <li key={i}>
              <strong>{String(r.severity || "risk")}</strong>
              <span>{String(r.title || r.detail || "").slice(0, 120)}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <ul className="twin-blast__nodes">
        {blast.slice(0, 12).map((b, i) => (
          <li key={`${b.title}-${i}`}>
            <span>{b.category}</span>
            <strong title={b.path || undefined}>{b.title}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}
