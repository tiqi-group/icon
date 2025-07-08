import {
  Typography,
  Stack,
  Table,
  TableHead,
  TableRow,
  TableCell,
  TableBody,
} from "@mui/material";
import { ReachabilityIndicator } from "../devices/ReachabilityIndicator";
import { DeviceStatus } from "../../types/enums";
import { DeviceInfo } from "../../types/DeviceInfo";

import LaunchIcon from "@mui/icons-material/Launch";
import IconButton from "@mui/material/IconButton";
import { Link as RouterLink } from "react-router";

interface DevicesStatusCardProps {
  enabledDevices: [string, DeviceInfo][];
  disabledDevices: [string, DeviceInfo][];
}

export const DevicesStatusCard = ({
  enabledDevices,
  disabledDevices,
}: DevicesStatusCardProps) => {
  return (
    <Stack spacing={1}>
      <IconButton
        component={RouterLink}
        to="/devices"
        sx={{ position: "absolute", top: 8, right: 8 }}
        size="small"
        aria-label="Open Devices Page"
      >
        <LaunchIcon fontSize="small" />
      </IconButton>

      <Typography variant="h6" gutterBottom>
        Devices
      </Typography>
      <div style={{ maxHeight: 300, overflow: "auto" }}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Status</TableCell>
              <TableCell>Name</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {[...enabledDevices, ...disabledDevices].map(([name, info]) => (
              <TableRow key={name}>
                <TableCell>
                  <ReachabilityIndicator
                    enabled={info.status === DeviceStatus.ENABLED}
                    reachable={info.reachable}
                  />
                </TableCell>
                <TableCell>{name}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </Stack>
  );
};
