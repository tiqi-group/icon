import { useEffect, useRef } from "react";

/**
 * Returns a ref for the selected list item and scrolls that item into view once, when
 * `ready` first becomes true. An item not rendered by then is left alone.
 */
export function useScrollIntoViewOnce<T extends HTMLElement>(ready: boolean) {
  const ref = useRef<T>(null);
  const done = useRef(false);

  useEffect(() => {
    if (!ready || done.current) return;
    done.current = true;
    ref.current?.scrollIntoView({ block: "center" });
  }, [ready]);

  return ref;
}
