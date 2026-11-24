import { MenuItem, Select, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { useBrowserSetting } from "../../hooks/useBrowserSetting";
import { fetchUserStyles, NO_USER_STYLE, USER_STYLE_KEY } from "../../utils/userStyle";
import { HelpButton } from "../HelpButtonComponent";

export const UserStyleSelect = () => {
  const [userStyle, setUserStyle] = useBrowserSetting(USER_STYLE_KEY, NO_USER_STYLE);
  const [available, setAvailable] = useState<string[]>([]);

  useEffect(() => {
    fetchUserStyles()
      .then(setAvailable)
      .catch(() => setAvailable([]));
  }, []);

  // Keep a selected style listed even if its directory is gone, so it can be unselected
  const styles =
    userStyle === NO_USER_STYLE || available.includes(userStyle)
      ? available
      : [...available, userStyle];

  return (
    <div style={{ display: "flex", alignItems: "center", padding: "4px 0" }}>
      <div style={{ display: "flex", alignItems: "center" }}>
        <Typography noWrap>Style</Typography>
        <HelpButton docString="Stylesheet applied in this browser. Further styles can be added as subdirectories with an index.css to the styles directory, by default next to the ICON configuration file." />
      </div>
      <Select
        size="small"
        displayEmpty
        value={userStyle}
        onChange={(e) => setUserStyle(e.target.value)}
      >
        <MenuItem value={NO_USER_STYLE}>Default</MenuItem>
        {styles.map((name) => (
          <MenuItem key={name} value={name}>
            {name}
          </MenuItem>
        ))}
      </Select>
    </div>
  );
};
