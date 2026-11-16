import { useId, useMemo } from "react";
import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from "@mui/material";
import { ExperimentMetadata } from "../../types/ExperimentMetadata";
import {
  SavedScanParameter,
  resultScanIdentity,
  resultScanKey,
  resultScanSpacing,
  scanBounds,
} from "../../utils/resultScanParameters";
import "./ResultScanParameters.css";

function SavedField({
  label,
  value,
  unit,
  title,
  helperText,
}: {
  label: string;
  value: string;
  unit?: string;
  title?: string;
  helperText?: string;
}) {
  const labelId = useId();
  return (
    <div className="result-scan-field">
      <dt id={labelId}>{unit ? `${label} (${unit})` : label}</dt>
      <dd aria-labelledby={labelId} title={title}>
        {value}
      </dd>
      {helperText && <small>{helperText}</small>}
    </div>
  );
}

/** A read-only summary derived from the job’s submitted scan values. */
export function ResultScanParameters({
  parameters,
  scanParameters,
  experimentId,
}: {
  parameters: ExperimentMetadata["parameters"];
  scanParameters: SavedScanParameter[];
  experimentId?: string;
}) {
  const scans = useMemo(
    () =>
      scanParameters.flatMap((scan, index) =>
        scan.realtime
          ? []
          : [
              {
                scan,
                index,
                identity: resultScanIdentity(scan, parameters, experimentId),
                bounds: scanBounds(scan.scan_values),
                spacing: resultScanSpacing(scan.scan_values),
              },
            ],
      ),
    [scanParameters, parameters, experimentId],
  );
  if (!scans.length) return null;
  return (
    <Box className="result-scan-frame">
      <TableContainer
        component={Paper}
        className="result-scan-parameters"
        sx={{
          border: 1,
          borderColor: "divider",
          boxShadow: "none",
          "& .result-scan-identity": {
            bgcolor: "action.hover",
            borderColor: "divider",
          },
          "& .result-scan-metrics": { borderColor: "divider" },
          "& dt, & small": { color: "text.secondary" },
        }}
      >
        <Table size="small" aria-label="Scan Parameters" sx={{ tableLayout: "fixed" }}>
          <colgroup>
            <col style={{ width: 38 }} />
            <col />
          </colgroup>
          <TableHead>
            <TableRow>
              <TableCell colSpan={2}>
                <Typography>Scan Parameters</Typography>
                <Typography variant="caption" color="text.secondary">
                  Submitted scan settings
                </Typography>
              </TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {scans.map(({ scan, index, identity, bounds, spacing }) => {
              const span = bounds ? bounds[1] - bounds[0] : NaN;
              const center = bounds
                ? Number.isFinite(span)
                  ? bounds[0] + span / 2
                  : bounds[0] / 2 + bounds[1] / 2
                : NaN;
              return (
                <TableRow key={scan.id ?? resultScanKey(scan)}>
                  <TableCell>{index + 1}</TableCell>
                  <TableCell>
                    <Box
                      component="section"
                      aria-label={`Scan ${index + 1}`}
                      className="result-scan-row"
                    >
                      <dl className="result-scan-identity">
                        <SavedField
                          label="Namespace"
                          value={identity.namespaceLabel}
                          title={identity.namespace}
                          helperText={
                            identity.namespace !== identity.namespaceLabel
                              ? identity.namespace
                              : undefined
                          }
                        />
                        <SavedField
                          label={identity.groupLabel}
                          value={identity.group}
                          helperText={
                            identity.groupFromIdentifier
                              ? "From saved parameter ID"
                              : undefined
                          }
                        />
                        <SavedField
                          label="Parameter"
                          value={identity.name}
                          title={scan.variable_id}
                        />
                      </dl>
                      <div className="result-scan-details">
                        <dl className="result-scan-range">
                          {bounds ? (
                            <>
                              <SavedField
                                label="Min"
                                value={String(bounds[0])}
                                unit={identity.unit}
                              />
                              <SavedField
                                label="Max"
                                value={String(bounds[1])}
                                unit={identity.unit}
                              />
                            </>
                          ) : (
                            <SavedField
                              label="Values"
                              value={
                                scan.scan_values.length
                                  ? scan.scan_values
                                      .map((value) =>
                                        typeof value === "string"
                                          ? JSON.stringify(value)
                                          : String(value),
                                      )
                                      .join(", ")
                                  : "Range unavailable"
                              }
                            />
                          )}
                        </dl>
                        <dl className="result-scan-metrics">
                          <SavedField
                            label="Points"
                            value={String(scan.scan_values.length)}
                          />
                          <SavedField
                            label="Span"
                            value={spacing.span}
                            unit={identity.unit}
                          />
                          <SavedField
                            label="Center"
                            value={
                              Number.isFinite(center) ? String(center) : "Unavailable"
                            }
                            unit={identity.unit}
                          />
                          <SavedField
                            label="Step size"
                            value={spacing.step}
                            unit={
                              Number.isFinite(Number(spacing.step))
                                ? identity.unit
                                : undefined
                            }
                            helperText={
                              spacing.reordered
                                ? "Grid spacing; scan order varies"
                                : undefined
                            }
                          />
                        </dl>
                      </div>
                    </Box>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
