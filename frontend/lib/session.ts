const SESSION_KEY = "imb_anon_session_id";

export function getOrCreateSessionId(): string {
  if (typeof window === "undefined") {
    return "";
  }

  const existing = window.localStorage.getItem(SESSION_KEY);
  if (existing) {
    return existing;
  }

  const sessionId = crypto.randomUUID();
  window.localStorage.setItem(SESSION_KEY, sessionId);
  return sessionId;
}

export function saveSessionId(sessionId: string): void {
  if (typeof window === "undefined" || !sessionId) {
    return;
  }
  window.localStorage.setItem(SESSION_KEY, sessionId);
}
