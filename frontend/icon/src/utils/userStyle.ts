import { forwardedPrefix } from "../socket";

export const USER_STYLE_KEY = "userStyle";
export const NO_USER_STYLE = "";

const LINK_ID = "icon-user-style";

const STYLES_URL = `${forwardedPrefix}/styles`;

const styleUrl = (name: string) =>
  `${STYLES_URL}/${encodeURIComponent(name)}/index.css`;

/** The style selected in this browser, as stored by `useBrowserSetting`. */
export const getStoredUserStyle = (): string => {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(USER_STYLE_KEY) ?? "");
    return typeof parsed === "string" ? parsed : NO_USER_STYLE;
  } catch {
    return NO_USER_STYLE;
  }
};

export const fetchUserStyles = async (): Promise<string[]> => {
  const response = await fetch(`${STYLES_URL}/`);
  if (!response.ok) throw new Error(`Failed to list styles: ${response.status}`);
  return (await response.json()) as string[];
};

/**
 * Applies the given user style to the page, replacing the previous one. Resolves once
 * the stylesheet is loaded or failed to load.
 */
export const applyUserStyle = (name: string): Promise<void> => {
  const current = document.getElementById(LINK_ID) as HTMLLinkElement | null;
  const href = name === NO_USER_STYLE ? null : styleUrl(name);
  if ((current?.getAttribute("href") ?? null) === href) return Promise.resolve();

  current?.remove();
  if (href === null) return Promise.resolve();

  return new Promise((resolve) => {
    const link = document.createElement("link");
    link.id = LINK_ID;
    link.rel = "stylesheet";
    link.href = href;
    link.onload = () => resolve();
    link.onerror = () => resolve();
    // MUI adds its styles to the end of <head> while the app runs. In <body> the user
    // style stays behind all of them, so it wins over MUI rules of equal specificity.
    document.body.appendChild(link);
  });
};
