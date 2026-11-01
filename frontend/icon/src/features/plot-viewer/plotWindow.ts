/** Request a compact popup; preserve the ordinary link if opening is blocked. */
export function tryOpenPlotWindow(
  url: string,
  host: Pick<Window, "open"> = window,
): boolean {
  let popup: Window | null;
  try {
    popup = host.open(
      "",
      "_blank",
      "popup=yes,toolbar=no,location=no,status=no,menubar=no,scrollbars=yes,resizable=yes,width=1100,height=800",
    );
  } catch {
    return false;
  }
  if (!popup) return false;
  try {
    // Open blank first so the destination never receives an opener reference.
    // Using the noopener feature would return null even on success, making a
    // blocked popup indistinguishable from an opened one for link fallback.
    popup.opener = null;
    popup.location.replace(url);
    return true;
  } catch {
    popup.close();
    return false;
  }
}
