"use client";

import { useEffect, useState } from "react";
import {
  clearUser,
  defaultUser,
  isAdmin,
  loadUser,
  saveUser,
  type UserProfile,
} from "@/lib/user";

export { isAdmin };

export function useUser() {
  const [user, setUser] = useState<UserProfile>(defaultUser);

  useEffect(() => {
    setUser(loadUser());
    const onUpdate = (e: Event) => {
      const detail = (e as CustomEvent<UserProfile>).detail;
      if (detail) setUser(detail);
      else setUser(loadUser());
    };
    window.addEventListener("spixa:user", onUpdate);
    window.addEventListener("evolve:user", onUpdate); // legacy
    window.addEventListener("storage", onUpdate);
    return () => {
      window.removeEventListener("spixa:user", onUpdate);
      window.removeEventListener("evolve:user", onUpdate);
      window.removeEventListener("storage", onUpdate);
    };
  }, []);

  function update(patch: Partial<UserProfile>) {
    const next = { ...user, ...patch };
    setUser(next);
    saveUser(next);
  }

  function signOut() {
    clearUser();
    setUser(defaultUser);
  }

  return { user, update, signOut };
}

/** Alias for components that only need profile + admin check */
export function useUserSafe() {
  return useUser();
}
