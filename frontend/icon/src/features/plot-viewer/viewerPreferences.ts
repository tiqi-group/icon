const WINDOW_SIZE_KEY = "icon.plotViewer.windowSize";
export function readViewerWindowSize(storage?: Pick<Storage, "getItem">): number {
  try {
    const value = Number((storage ?? localStorage).getItem(WINDOW_SIZE_KEY));
    return Number.isSafeInteger(value) && value >= 1 && value <= 100000 ? value : 1000;
  } catch {
    return 1000;
  }
}
export function rememberViewerWindowSize(
  value: number,
  storage?: Pick<Storage, "setItem">,
) {
  try {
    (storage ?? localStorage).setItem(WINDOW_SIZE_KEY, String(value));
  } catch {
    /* Viewing works when browser storage is unavailable. */
  }
}
