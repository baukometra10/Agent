export default function Loading() {
  return (
    <div className="route-loading" aria-busy="true" aria-live="polite">
      <div className="route-loading__bar" />
      <div className="route-loading__stack">
        <div className="route-loading__block is-title" />
        <div className="route-loading__block" />
        <div className="route-loading__block is-wide" />
      </div>
    </div>
  );
}
