"use client";

import { useState } from "react";

type Decision = "approve" | "reject" | "revise" | null;

export function ProposalActions() {
  const [decision, setDecision] = useState<Decision>(null);
  const [note, setNote] = useState<string | null>(null);

  function act(next: Decision) {
    setDecision(next);
    if (next === "approve") {
      setNote("تم تسجيل الموافقة محليًا — الحفظ في الخادم سيُفعّل في المرحلة 7.");
    } else if (next === "reject") {
      setNote("تم تسجيل الرفض محليًا — الحفظ في الخادم سيُفعّل في المرحلة 7.");
    } else if (next === "revise") {
      setNote("تم طلب التعديل محليًا — الحفظ في الخادم سيُفعّل في المرحلة 7.");
    }
  }

  return (
    <div className="proposal-actions">
      <div className="proposal-actions__row">
        <button
          type="button"
          className="btn btn-success"
          disabled={decision !== null}
          onClick={() => act("approve")}
        >
          موافقة
        </button>
        <button
          type="button"
          className="btn btn-danger"
          disabled={decision !== null}
          onClick={() => act("reject")}
        >
          رفض
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={decision !== null}
          onClick={() => act("revise")}
        >
          طلب تعديل
        </button>
      </div>
      {note && <p className="proposal-actions__note">{note}</p>}
    </div>
  );
}
