/** Cursor-style short topic titles for agent chat tabs. */

const PLACEHOLDERS = new Set(
  ["أمر جديد", "Agent", "Agent session", "New Agent", "New chat", "Chat", "Untitled", "أمر محفوظ"].map((s) =>
    s.toLowerCase(),
  ),
);

export function isPlaceholderTitle(title: string | null | undefined): boolean {
  const t = (title || "").trim().toLowerCase();
  return !t || PLACEHOLDERS.has(t);
}

export function topicTitleFromMessage(raw: string, maxLen = 48): string {
  let text = (raw || "").trim();
  const marker = "طلب المستخدم:";
  if (text.includes(marker)) text = text.split(marker).pop()!.trim();

  text = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .filter((l) => !l.startsWith("[mode:"))
    .filter((l) => !l.startsWith("أنت وكيل"))
    .join(" ");

  text = text.replace(/\s+/g, " ").trim();

  for (const prefix of [
    "من فضلك ",
    "رجاءً ",
    "رجاءا ",
    "لو سمحت ",
    "أريد ",
    "ابي ",
    "أبغى ",
    "please ",
    "can you ",
    "could you ",
    "i want ",
    "i need ",
    "help me ",
  ]) {
    if (text.toLowerCase().startsWith(prefix)) {
      text = text.slice(prefix.length).replace(/^[،,\s]+/, "");
      break;
    }
  }

  if (!text) return "أمر جديد";
  if (text.length <= maxLen) return text;
  let cut = text.slice(0, maxLen - 1);
  const sp = cut.lastIndexOf(" ");
  if (sp > 12) cut = cut.slice(0, sp);
  return `${cut.replace(/[.,،؛:]+$/, "")}…`;
}
