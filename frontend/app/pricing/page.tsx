import { Suspense } from "react";
import PricingView from "./PricingView";

export default function PricingPage() {
  return (
    <Suspense fallback={<div className="pricing-page">جاري التحميل…</div>}>
      <PricingView />
    </Suspense>
  );
}