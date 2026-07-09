import { useMemo } from "react";
import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from "@mui/material";
import { ExperimentData } from "../../types/ExperimentData";
import { ScanParameter } from "../../types/ScanParameter";

const TIMESTAMP_KEY = "timestamp";

function formatCell(value: number | boolean | string | undefined): string {
  if (value === undefined) return "—";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return String(value);
    // Show a compact but precise representation for floats.
    return Number.isInteger(value) ? String(value) : value.toPrecision(6);
  }
  return String(value);
}

/**
 * Tabular view of the scalar result-channel data behind a plot window.
 *
 * Renders one row per data-point index, with columns for every scan parameter
 * (timestamp first) followed by each result channel in this window. It consumes
 * the same (already truncated) `experimentData` that feeds `ResultChannelPlot`,
 * so no additional data fetching is required.
 */
export const ResultChannelTable = ({
  experimentData,
  channelNames,
  scanParameters,
}: {
  experimentData: ExperimentData;
  channelNames: string[];
  scanParameters?: ScanParameter[];
}) => {
  // Human-readable label for a scan-parameter key, falling back to the raw key.
  const scanParamLabel = useMemo(() => {
    const labels: Record<string, string> = {};
    for (const param of scanParameters ?? []) {
      labels[param.variable_id] = param.name || param.variable_id;
    }
    return labels;
  }, [scanParameters]);

  // Column order for scan parameters: timestamp first, then the rest.
  const scanParamKeys = useMemo(() => {
    const keys = Object.keys(experimentData.scan_parameters ?? {});
    return keys.sort((a, b) => {
      if (a === TIMESTAMP_KEY) return -1;
      if (b === TIMESTAMP_KEY) return 1;
      return a.localeCompare(b);
    });
  }, [experimentData.scan_parameters]);

  // Row indices: union of data-point indices present across this window's channels.
  const rowIndices = useMemo(() => {
    const indices = new Set<number>();
    for (const channel of channelNames) {
      const channelData = experimentData.result_channels?.[channel];
      if (!channelData) continue;
      for (const key of Object.keys(channelData)) {
        indices.add(Number(key));
      }
    }
    return Array.from(indices).sort((a, b) => a - b);
  }, [experimentData.result_channels, channelNames]);

  return (
    <TableContainer component={Paper} sx={{ maxHeight: 400, overflow: "auto" }}>
      <Table stickyHeader size="small">
        <TableHead>
          <TableRow>
            <TableCell>#</TableCell>
            {scanParamKeys.map((key) => (
              <TableCell key={`param-${key}`}>
                {key === TIMESTAMP_KEY ? "timestamp" : (scanParamLabel[key] ?? key)}
              </TableCell>
            ))}
            {channelNames.map((channel) => (
              <TableCell key={`channel-${channel}`} align="right">
                {channel}
              </TableCell>
            ))}
          </TableRow>
        </TableHead>
        <TableBody>
          {rowIndices.map((idx) => {
            const key = String(idx);
            return (
              <TableRow key={idx}>
                <TableCell>{idx}</TableCell>
                {scanParamKeys.map((paramKey) => (
                  <TableCell key={`param-${paramKey}`}>
                    {formatCell(experimentData.scan_parameters[paramKey]?.[key])}
                  </TableCell>
                ))}
                {channelNames.map((channel) => (
                  <TableCell key={`channel-${channel}`} align="right">
                    {formatCell(experimentData.result_channels[channel]?.[key])}
                  </TableCell>
                ))}
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
};

export default ResultChannelTable;
