import { useEffect } from "react";
import { useLocation } from "react-router";

// Pages that keep their selection in the URL query
const PAGES = ["/experiments", "/data", "/devices", "/settings"];

/**
 * Remembers the last query of each page for this browser tab. When a page is
 * opened without a query, e.g. from the sidebar, returns its last URL so that
 * the previous selection can be restored.
 */
export function useRestoredPageUrl(): string | null {
  const { pathname, search } = useLocation();
  const storageKey = `lastSearch:${pathname}`;
  const remembered = PAGES.includes(pathname);

  useEffect(() => {
    if (remembered && search) sessionStorage.setItem(storageKey, search);
  }, [remembered, storageKey, search]);

  const lastSearch = remembered && !search ? sessionStorage.getItem(storageKey) : null;
  return lastSearch ? pathname + lastSearch : null;
}
