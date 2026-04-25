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

// Default operator on first load (no localStorage entry yet). The
// OperatorSwitcher overrides this once the user picks one.
const DEFAULT_OPERATOR_ID = "op-senior";

export function authHeaders(): Record<string, string> {
  const id = currentOperatorId() ?? DEFAULT_OPERATOR_ID;
  return { "X-Operator-Id": id };
}
