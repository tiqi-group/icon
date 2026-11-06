// Notifies the storage hooks in this window; other windows get a storage event
const listeners = new Set<() => void>();

/**
 * Subscribes to changes of localStorage and sessionStorage made in this window, and of
 * localStorage made in other windows.
 */
export const subscribeToStorage = (listener: () => void) => {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
};

/** Tells the subscribers in this window that localStorage or sessionStorage changed. */
export const notifyStorageChange = () => listeners.forEach((listener) => listener());
