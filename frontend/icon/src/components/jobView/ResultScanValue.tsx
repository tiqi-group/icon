import { Box, Chip, Typography } from "@mui/material";
import { HelpButton } from "../HelpButtonComponent";
import { ParameterValueType } from "../../types/ExperimentMetadata";

/** Keep the recorded scalar visible beside its saved scan-axis marker. */
export function ResultScanValue({
  parameterId,
  label,
  scanIndex,
  value,
}: {
  parameterId: string;
  label: string;
  scanIndex: number;
  value?: ParameterValueType;
}) {
  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        flexWrap: "wrap",
        gap: 1,
        py: 0.5,
        minWidth: 0,
      }}
    >
      <Box sx={{ display: "flex", alignItems: "center", minWidth: 0 }}>
        <Typography sx={{ overflowWrap: "anywhere" }}>{label}</Typography>
        <HelpButton docString={parameterId} />
      </Box>
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: 1,
          minWidth: 0,
        }}
      >
        <Chip
          label={`Scan ${scanIndex + 1}`}
          color="primary"
          size="small"
          variant="outlined"
        />
        <Typography
          component="span"
          variant="body2"
          color="text.secondary"
          aria-label={`${label} recorded value`}
          title="Recorded parameter value"
          sx={{
            minWidth: 0,
            overflowWrap: "anywhere",
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {value == null ? "Not recorded" : String(value)}
        </Typography>
      </Box>
    </Box>
  );
}
