export type UserRole = "user" | "admin";

export type UserPlan = "free" | "pro" | "team" | "enterprise";

export type UserProfile = {
  name: string;
  role: string;
  email: string;
  avatarUrl: string;
  /** Access level — admin sees system ownership/training */
  access: UserRole;
  plan: UserPlan;
  /** Usage tokens (monthly allowance) */
  tokensRemaining: number;
  tokensMonthly: number;
  /** Features unlocked after confirmed payment */
  entitlements: string[];
  sessionToken: string;
  signedIn: boolean;
};

const KEY = "spixa.userProfile";
const LEGACY_KEY = "evolve.userProfile";

/** Features a normal member can use without admin. */
export const USER_FEATURES = [
  "chat",
  "projects",
  "proposals",
  "execution",
  "copilot",
  "understanding",
  "analysis",
  "knowledge",
  "roadmap",
  "agents_view",
] as const;

/** Admin-only capabilities (training, ownership, fleet, self-heal). */
export const ADMIN_FEATURES = [
  "admin_console",
  "model_training",
  "ownership",
  "fleet",
  "self_maintain",
  "billing_ops",
] as const;

export const defaultUser: UserProfile = {
  name: "زائر",
  role: "عضو",
  email: "",
  avatarUrl: "",
  access: "user",
  plan: "free",
  tokensRemaining: 0,
  tokensMonthly: 0,
  entitlements: [],
  sessionToken: "",
  signedIn: false,
};

export function loadUser(): UserProfile {
  if (typeof window === "undefined") return defaultUser;
  try {
    let raw = localStorage.getItem(KEY);
    if (!raw) {
      raw = localStorage.getItem(LEGACY_KEY);
      if (raw) {
        localStorage.setItem(KEY, raw);
        localStorage.removeItem(LEGACY_KEY);
      }
    }
    if (!raw) return defaultUser;
    return { ...defaultUser, ...JSON.parse(raw) };
  } catch {
    return defaultUser;
  }
}

export function saveUser(profile: UserProfile) {
  localStorage.setItem(KEY, JSON.stringify(profile));
  window.dispatchEvent(new CustomEvent("spixa:user", { detail: profile }));
}

export function clearUser() {
  localStorage.removeItem(KEY);
  localStorage.removeItem(LEGACY_KEY);
  window.dispatchEvent(new CustomEvent("spixa:user", { detail: defaultUser }));
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return "؟";
  if (parts.length === 1) return parts[0].slice(0, 2);
  return `${parts[0][0]}${parts[1][0]}`;
}

export function isAdmin(user: UserProfile): boolean {
  return user.access === "admin" && user.signedIn;
}

export function hasFeature(user: UserProfile, feature: string): boolean {
  if (!user.signedIn) return false;
  if (isAdmin(user)) return true;
  if ((ADMIN_FEATURES as readonly string[]).includes(feature)) return false;
  return user.entitlements.includes(feature);
}

export function hasTokens(user: UserProfile, cost = 1): boolean {
  if (isAdmin(user)) return true;
  return user.tokensRemaining >= cost;
}
