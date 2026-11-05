import type { FileEdit } from "@/lib/agentEdits";

export type LineDiff = {
  type: "same" | "add" | "del";
  text: string;
};

export type TabSnapshot = {
  id: string;
  title: string;
  reply: string;
  edits: FileEdit[];
};

export type TabCompareResult = {
  left: TabSnapshot;
  right: TabSnapshot;
  replyDiff: LineDiff[];
  filesOnlyLeft: string[];
  filesOnlyRight: string[];
  filesBoth: string[];
  contentChanged: string[];
};

export type DiffHunk = {
  startOld: number;
  startNew: number;
  lines: Array<LineDiff & { oldNo: number | null; newNo: number | null }>;
};

export function diffStats(rows: LineDiff[]): { adds: number; dels: number } {
  let adds = 0;
  let dels = 0;
  for (const r of rows) {
    if (r.type === "add") adds++;
    else if (r.type === "del") dels++;
  }
  return { adds, dels };
}

/** Keep changed regions ± context lines for Cursor-like review cards. */
export function hunksFromDiff(rows: LineDiff[], context = 2): DiffHunk[] {
  const marked = rows.map((r) => r.type !== "same");
  const keep = new Array(rows.length).fill(false);
  for (let i = 0; i < rows.length; i++) {
    if (!marked[i]) continue;
    for (let j = Math.max(0, i - context); j <= Math.min(rows.length - 1, i + context); j++) {
      keep[j] = true;
    }
  }
  const hunks: DiffHunk[] = [];
  let oldNo = 1;
  let newNo = 1;
  let i = 0;
  while (i < rows.length) {
    if (!keep[i]) {
      if (rows[i].type === "same") {
        oldNo++;
        newNo++;
      } else if (rows[i].type === "del") oldNo++;
      else newNo++;
      i++;
      continue;
    }
    const startOld = oldNo;
    const startNew = newNo;
    const lines: DiffHunk["lines"] = [];
    while (i < rows.length && keep[i]) {
      const r = rows[i];
      if (r.type === "same") {
        lines.push({ ...r, oldNo, newNo });
        oldNo++;
        newNo++;
      } else if (r.type === "del") {
        lines.push({ ...r, oldNo, newNo: null });
        oldNo++;
      } else {
        lines.push({ ...r, oldNo: null, newNo });
        newNo++;
      }
      i++;
    }
    hunks.push({ startOld, startNew, lines });
  }
  return hunks;
}

/** Simple line LCS diff — good enough for chat reply comparison. */
export function lineDiff(a: string, b: string): LineDiff[] {
  const A = (a || "").split(/\r?\n/);
  const B = (b || "").split(/\r?\n/);
  const n = A.length;
  const m = B.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const out: LineDiff[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (A[i] === B[j]) {
      out.push({ type: "same", text: A[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      out.push({ type: "del", text: A[i++] });
    } else {
      out.push({ type: "add", text: B[j++] });
    }
  }
  while (i < n) out.push({ type: "del", text: A[i++] });
  while (j < m) out.push({ type: "add", text: B[j++] });
  return out;
}

export function compareTabs(left: TabSnapshot, right: TabSnapshot): TabCompareResult {
  const lMap = new Map(left.edits.map((e) => [e.path, e.content]));
  const rMap = new Map(right.edits.map((e) => [e.path, e.content]));
  const all = new Set([...lMap.keys(), ...rMap.keys()]);
  const filesOnlyLeft: string[] = [];
  const filesOnlyRight: string[] = [];
  const filesBoth: string[] = [];
  const contentChanged: string[] = [];
  for (const p of all) {
    const L = lMap.has(p);
    const R = rMap.has(p);
    if (L && !R) filesOnlyLeft.push(p);
    else if (!L && R) filesOnlyRight.push(p);
    else {
      filesBoth.push(p);
      if ((lMap.get(p) || "") !== (rMap.get(p) || "")) contentChanged.push(p);
    }
  }
  return {
    left,
    right,
    replyDiff: lineDiff(left.reply, right.reply),
    filesOnlyLeft: filesOnlyLeft.sort(),
    filesOnlyRight: filesOnlyRight.sort(),
    filesBoth: filesBoth.sort(),
    contentChanged: contentChanged.sort(),
  };
}
