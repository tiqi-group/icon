import { useMemo } from "react";
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
} from "@mui/material";
import { ExperimentData } from "../../types/ExperimentData";
import { ScanParameter } from "../../types/ScanParameter";
import { formatDateTime, formatTime, hasDayBreak } from "../../utils/timeUtils";

const TIMESTAMP_KEY = "timestamp";
const MAX_ROWS = 200;

// Clamp header labels to one line. Unlike nowrap, this lets a column shrink below its
// label, so labels only get an ellipsis once the table runs out of room.
const headerLabelSx = {
  display: "-webkit-box",
  WebkitLineClamp: 1,
  WebkitBoxOrient: "vertical",
  overflow: "hidden",
  whiteSpace: "normal",
  wordBreak: "break-all",
} as const;

function formatCell(value: number | boolean | string | undefined): string {
  if (value === undefined) return "—";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return String(value);
    // Show a compact but precise representation for floats.
    return Number.isInteger(value)
      ? String(value)
      : String(Number(value.toPrecision(6)));
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
  windowSize = null,
}: {
  experimentData: ExperimentData;
  channelNames: string[];
  scanParameters?: ScanParameter[];
  windowSize?: number | null;
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
  const allIndices = useMemo(() => {
    const indices = new Set<number>();
    for (const channel of channelNames) {
      const channelData = experimentData.readouts.result_channels?.[channel];
      if (!channelData) continue;
      for (const key of Object.keys(channelData)) {
        indices.add(Number(key));
      }
    }
    return Array.from(indices).sort((a, b) => a - b);
  }, [experimentData.readouts.result_channels, channelNames]);

  // Only render the most recent rows, like the plot does for its window size.
  const rowIndices = allIndices.slice(-Math.min(windowSize ?? MAX_ROWS, MAX_ROWS));

  const timestamps = experimentData.scan_parameters[TIMESTAMP_KEY];
  const formatTimestamp = hasDayBreak(
    rowIndices.map((idx) => String(timestamps?.[idx])),
  )
    ? formatDateTime
    : formatTime;

  return (
    <>
      <TableContainer component={Paper} sx={{ maxHeight: 400, overflow: "auto" }}>
        <Table
          stickyHeader
          size="small"
          sx={{ "& .MuiTableCell-root": { px: 1, whiteSpace: "nowrap" } }}
        >
          <TableHead>
            <TableRow>
              <TableCell>#</TableCell>
              {scanParamKeys.map((key) => {
                const label =
                  key === TIMESTAMP_KEY ? "timestamp" : (scanParamLabel[key] ?? key);
                return (
                  <TableCell key={`param-${key}`} title={label}>
                    <Box sx={headerLabelSx}>{label}</Box>
                  </TableCell>
                );
              })}
              {channelNames.map((channel) => (
                <TableCell key={`channel-${channel}`} align="right" title={channel}>
                  <Box sx={headerLabelSx}>{channel}</Box>
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
                  {scanParamKeys.map((paramKey) => {
                    const value = experimentData.scan_parameters[paramKey]?.[key];
                    return (
                      <TableCell key={`param-${paramKey}`}>
                        {paramKey === TIMESTAMP_KEY && value !== undefined
                          ? formatTimestamp(String(value))
                          : formatCell(value)}
                      </TableCell>
                    );
                  })}
                  {channelNames.map((channel) => (
                    <TableCell key={`channel-${channel}`} align="right">
                      {formatCell(
                        experimentData.readouts.result_channels[channel]?.[key],
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
      {rowIndices.length < allIndices.length && (
        <Typography variant="caption" color="text.secondary">
          Showing last {rowIndices.length} of {allIndices.length} rows
        </Typography>
      )}
    </>
  );
};

export default ResultChannelTable;
