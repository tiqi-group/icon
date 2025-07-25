import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import LockOpenIcon from "@mui/icons-material/LockOpen";
import LockIcon from "@mui/icons-material/Lock";
import Stack from "@mui/material/Stack";
import { ThemeSwitcher } from "@toolpad/core/DashboardLayout";
import { socket } from "../../socket";
import { useControlState } from "../../hooks/useControlState";

export function ToolbarActionsTakeControl() {
  const { controllingSid, socketioSID } = useControlState();

  const hasControl = controllingSid === socketioSID;

  const handleClick = () => {
    if (hasControl) {
      socket.emit("release_control");
    } else {
      socket.emit("take_control");
    }
  };

  return (
    <Stack direction="row" spacing={1}>
      <Tooltip title={hasControl ? "Release Control" : "Take Control"}>
        <IconButton color="inherit" onClick={handleClick}>
          {hasControl ? <LockIcon /> : <LockOpenIcon />}
        </IconButton>
      </Tooltip>
      <ThemeSwitcher />
    </Stack>
  );
}
