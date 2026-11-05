"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { AppShell } from "./AppShell";
import { featureForPath } from "@/lib/billing";
import { loadUser, isAdmin, hasFeature } from "@/lib/user";

const PUBLIC = new Set(["/login", "/pricing", "/download"]);

export function ShellGate({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const router = useRouter();
  const isPublic = PUBLIC.has(pathname);

  useEffect(() => {
    const user = loadUser();
    if (!user.signedIn && !isPublic) {
      router.replace("/login");
      return;
    }
    if (user.signedIn && pathname === "/login") {
      router.replace(isAdmin(user) ? "/admin" : "/");
      return;
    }
    if (
      user.signedIn &&
      !isAdmin(user) &&
      (pathname.startsWith("/admin") ||
        pathname.startsWith("/control-plane") ||
        pathname.startsWith("/maintain") ||
        pathname.startsWith("/settings"))
    ) {
      router.replace("/console");
      return;
    }
    const need = featureForPath(pathname);
    if (user.signedIn && need && !hasFeature(user, need)) {
      router.replace(`/pricing?need=${encodeURIComponent(need)}`);
    }
  }, [pathname, isPublic, router]);

  if (isPublic) {
    return <>{children}</>;
  }
  return <AppShell>{children}</AppShell>;
}
