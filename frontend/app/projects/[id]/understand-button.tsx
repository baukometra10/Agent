"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { API_URL } from "@/lib/api";

export function UnderstandButton({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/projects/${projectId}/understand`, {
        method: "POST",
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(body || "فشل الفهم");
      }
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "فشل");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="toolbar">
      <button type="button" className="btn btn-primary" onClick={run} disabled={loading}>
        {loading ? "جارٍ الفهم…" : "تشغيل الفهم"}
      </button>
      {error && <span style={{ color: "var(--danger)", fontSize: "0.88rem" }}>{error}</span>}
    </div>
  );
}
