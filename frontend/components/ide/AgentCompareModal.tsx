"use client";

import { compareTabs, type TabSnapshot } from "@/lib/agentPanel/tabDiff";

type Props = {
  left: TabSnapshot;
  right: TabSnapshot;
  onClose: () => void;
};

export function AgentCompareModal({ left, right, onClose }: Props) {
  const diff = compareTabs(left, right);
  return (
    <div className="ide-agent-compare" role="dialog" aria-modal="true">
      <button type="button" className="ide-agent-compare__backdrop" aria-label="إغلاق" onClick={onClose} />
      <div className="ide-agent-compare__panel">
        <header>
          <strong>مقارنة تبويبين</strong>
          <button type="button" onClick={onClose}>
            Done
          </button>
        </header>
        <div className="ide-agent-compare__cols">
          <section>
            <h4 dir="auto">{left.title}</h4>
            <pre dir="auto">{left.reply || "—"}</pre>
          </section>
          <section>
            <h4 dir="auto">{right.title}</h4>
            <pre dir="auto">{right.reply || "—"}</pre>
          </section>
        </div>
        <section className="ide-agent-compare__files">
          <h4>ملفات</h4>
          <ul>
            {diff.filesOnlyLeft.map((p) => (
              <li key={`l-${p}`}>
                <em>−</em> {p}
              </li>
            ))}
            {diff.filesOnlyRight.map((p) => (
              <li key={`r-${p}`}>
                <em>+</em> {p}
              </li>
            ))}
            {diff.contentChanged.map((p) => (
              <li key={`c-${p}`}>
                <em>△</em> {p}
              </li>
            ))}
            {!diff.filesOnlyLeft.length && !diff.filesOnlyRight.length && !diff.contentChanged.length ? (
              <li>—</li>
            ) : null}
          </ul>
        </section>
        <section className="ide-agent-compare__diff">
          <h4>فرق الرد</h4>
          <pre className="ide-agent-compare__diff-body">
            {diff.replyDiff.slice(0, 200).map((row, i) => (
              <span key={i} className={`is-${row.type}`}>
                {row.type === "add" ? "+ " : row.type === "del" ? "− " : "  "}
                {row.text}
                {"\n"}
              </span>
            ))}
          </pre>
        </section>
      </div>
    </div>
  );
}
