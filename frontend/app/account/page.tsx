"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Account hub lives on the web console (usage + billing + settings). */
export default function AccountRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/console");
  }, [router]);
  return null;
}
