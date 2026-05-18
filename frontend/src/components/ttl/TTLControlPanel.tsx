import Box from "@mui/material/Box";
import Typography from "@mui/material/Typography";
import { TTLChannel } from "./TTLChannel";
import { TTLState } from "../../hooks/useTTLState";

interface Props {
  ttl: TTLState;
}

export function TTLControlPanel({ ttl }: Props) {
  const { states, labels, localManualState, setState, setLocalManual, setLabel } = ttl;

  return (
    <Box sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        TTL Channels
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        <Box component="span" sx={{ color: "primary.main", fontWeight: "bold" }}>■</Box>
        {" "}FPGA control &nbsp;
        <Box component="span" sx={{ color: "success.main", fontWeight: "bold" }}>●</Box>
        {" "}ON &nbsp;
        <Box component="span" sx={{ color: "error.main", fontWeight: "bold" }}>●</Box>
        {" "}OFF &nbsp;— double-click a label to rename
      </Typography>
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: {
            xs: "1fr",
            sm: "repeat(2, 1fr)",
            md: "repeat(4, 1fr)",
            lg: "repeat(8, 1fr)",
          },
          gap: 0.75,
        }}
      >
        {states.map((state, channel) => (
          <TTLChannel
            key={channel}
            channel={channel}
            state={state}
            localManualState={localManualState[channel] as 0 | 1}
            label={labels[channel]}
            onSetState={(s) => setState(channel, s)}
            onSetLocalManual={(m) => setLocalManual(channel, m)}
            onSetLabel={(l) => setLabel(channel, l)}
          />
        ))}
      </Box>
    </Box>
  );
}
