import { Suspense } from "react";
import ConsoleView from "./ConsoleView";

export default function ConsolePage() {
  return (
    <Suspense fallback={<div className="web-console">جاري التحميل…</div>}>
      <ConsoleView />
    </Suspense>
  );
}
