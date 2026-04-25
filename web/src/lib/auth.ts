const STORAGE_KEY = "ngo-hub:operatorId";

export function currentOperatorId(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setCurrentOperatorId(id: string) {
  try {
    localStorage.setItem(STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
}

export function authHeaders(): Record<string, string> {
  const id = currentOperatorId();
  return id ? { "X-Operator-Id": id } : {};
}
