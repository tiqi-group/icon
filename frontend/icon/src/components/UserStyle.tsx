import { useEffect } from "react";
import { useBrowserSetting } from "../hooks/useBrowserSetting";
import { applyUserStyle, NO_USER_STYLE, USER_STYLE_KEY } from "../utils/userStyle";

/** Keeps the page's user style in sync with the browser setting. */
export const UserStyle = () => {
  const [userStyle] = useBrowserSetting(USER_STYLE_KEY, NO_USER_STYLE);

  useEffect(() => {
    void applyUserStyle(userStyle);
  }, [userStyle]);

  return null;
};
