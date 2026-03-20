import { useState } from "react";
import {
  Button,
  Card,
  CardContent,
  FormControl,
  Grid,
  InputLabel,
  MenuItem,
  Select,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Alert,
} from "@mui/material";
import { ExpandMore } from "@mui/icons-material";
import { ExperimentData, FitResult } from "../../types/ExperimentData";
import { runMethod } from "../../socket";
import { FIT_PARAM_NAMES, FIT_TYPES } from "../../utils/fitFunctions";

interface FitPanelProps {
  jobId: string;
  experimentData: ExperimentData;
  clickedX: number | null;
}

export default function FitPanel({ jobId, experimentData, clickedX }: FitPanelProps) {
  const channelNames = Object.keys(experimentData.result_channels);
  const [selectedChannel, setSelectedChannel] = useState<string>(channelNames[0] ?? "");
  const [funcType, setFuncType] = useState<string>("lorentzian");
  const [xMin, setXMin] = useState<string>("");
  const [xMax, setXMax] = useState<string>("");
  const [initOverrides, setInitOverrides] = useState<Record<string, string>>({});
  const [fitting, setFitting] = useState(false);

  const [updateParamId, setUpdateParamId] = useState<string>("");
  const [updateValue, setUpdateValue] = useState<string>("");

  const fit: FitResult | undefined = experimentData.fits[selectedChannel];
  const paramNames = FIT_PARAM_NAMES[funcType] ?? [];

  // Pre-fill x0 from click
  const effectiveInit = { ...initOverrides };
  if (clickedX !== null && paramNames.includes("x0") && !effectiveInit["x0"]) {
    effectiveInit["x0"] = String(clickedX);
  }

  const handleFit = () => {
    setFitting(true);
    const xRange =
      xMin !== "" && xMax !== "" ? [parseFloat(xMin), parseFloat(xMax)] : null;

    const init: Record<string, number> = {};
    for (const [key, val] of Object.entries(effectiveInit)) {
      if (val !== "") init[key] = parseFloat(val);
    }

    runMethod(
      "data.run_fit",
      [],
      {
        job_id: Number(jobId),
        result_channel: selectedChannel,
        func_type: funcType,
        x_range: xRange,
        init: Object.keys(init).length > 0 ? init : null,
      },
      () => setFitting(false),
    );
  };

  const handleDelete = () => {
    runMethod("data.delete_fit", [], {
      job_id: Number(jobId),
      result_channel: selectedChannel,
    });
  };

  const handleUpdateParameter = () => {
    if (!updateParamId || updateValue === "") return;
    runMethod("parameters.update_parameter_by_id", [
      updateParamId,
      parseFloat(updateValue),
    ]);
  };

  // Get scan parameter names for "update parameter" dropdown
  const scanParamKeys = Object.keys(experimentData.scan_parameters).filter(
    (k) => k !== "timestamp",
  );
  const allParamIds = Object.keys(experimentData.parameters);

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Curve Fitting
        </Typography>

        <Grid container spacing={2} alignItems="center">
          <Grid size={{ xs: 12, sm: 4 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Channel</InputLabel>
              <Select
                value={selectedChannel}
                label="Channel"
                onChange={(e) => setSelectedChannel(e.target.value)}
              >
                {channelNames.map((ch) => (
                  <MenuItem key={ch} value={ch}>
                    {ch}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 12, sm: 4 }}>
            <FormControl fullWidth size="small">
              <InputLabel>Model</InputLabel>
              <Select
                value={funcType}
                label="Model"
                onChange={(e) => {
                  setFuncType(e.target.value);
                  setInitOverrides({});
                }}
              >
                {FIT_TYPES.map((ft) => (
                  <MenuItem key={ft} value={ft}>
                    {ft}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>

          <Grid size={{ xs: 6, sm: 2 }}>
            <TextField
              size="small"
              label="X min"
              type="number"
              fullWidth
              value={xMin}
              onChange={(e) => setXMin(e.target.value)}
            />
          </Grid>
          <Grid size={{ xs: 6, sm: 2 }}>
            <TextField
              size="small"
              label="X max"
              type="number"
              fullWidth
              value={xMax}
              onChange={(e) => setXMax(e.target.value)}
            />
          </Grid>
        </Grid>

        <Accordion sx={{ mt: 1 }}>
          <AccordionSummary expandIcon={<ExpandMore />}>
            <Typography variant="body2">Initial parameter overrides</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Grid container spacing={1}>
              {paramNames.map((name) => (
                <Grid size={{ xs: 6, sm: 3 }} key={name}>
                  <TextField
                    size="small"
                    label={name}
                    type="number"
                    fullWidth
                    value={effectiveInit[name] ?? ""}
                    onChange={(e) =>
                      setInitOverrides((prev) => ({
                        ...prev,
                        [name]: e.target.value,
                      }))
                    }
                  />
                </Grid>
              ))}
            </Grid>
            {clickedX !== null && (
              <Typography variant="caption" sx={{ mt: 1, display: "block" }}>
                Clicked x = {clickedX.toFixed(4)} (used as x0 hint if not overridden)
              </Typography>
            )}
          </AccordionDetails>
        </Accordion>

        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <Button
            variant="contained"
            onClick={handleFit}
            disabled={fitting || !selectedChannel}
          >
            {fitting ? "Fitting..." : "Run Fit"}
          </Button>
          {fit && (
            <Button variant="outlined" color="error" onClick={handleDelete}>
              Delete Fit
            </Button>
          )}
        </div>

        {fit && (
          <div style={{ marginTop: 16 }}>
            {!fit.success && (
              <Alert severity="error" sx={{ mb: 1 }}>
                {fit.message}
              </Alert>
            )}
            {fit.success && (
              <>
                <Typography variant="subtitle2">
                  Fit Results ({fit.func_type})
                </Typography>
                <Table size="small" sx={{ maxWidth: 400 }}>
                  <TableHead>
                    <TableRow>
                      <TableCell>Parameter</TableCell>
                      <TableCell>Value</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {Object.entries(fit.result).map(([key, val]) => (
                      <TableRow key={key}>
                        <TableCell>{key}</TableCell>
                        <TableCell>{val.toFixed(6)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <Typography variant="subtitle2" sx={{ mt: 1 }}>
                  Goodness of Fit
                </Typography>
                <Table size="small" sx={{ maxWidth: 400 }}>
                  <TableBody>
                    {Object.entries(fit.goodness).map(([key, val]) => (
                      <TableRow key={key}>
                        <TableCell>{key}</TableCell>
                        <TableCell>{val.toFixed(6)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                <Typography variant="subtitle2" sx={{ mt: 2 }}>
                  Update Parameter
                </Typography>
                <Grid container spacing={1} alignItems="center" sx={{ mt: 0.5 }}>
                  <Grid size={{ xs: 5 }}>
                    <FormControl fullWidth size="small">
                      <InputLabel>Parameter</InputLabel>
                      <Select
                        value={updateParamId}
                        label="Parameter"
                        onChange={(e) => {
                          setUpdateParamId(e.target.value);
                        }}
                      >
                        {/* Show scan parameters first, then all parameters */}
                        {scanParamKeys.map((id) => (
                          <MenuItem key={id} value={id}>
                            {id} (scan)
                          </MenuItem>
                        ))}
                        {allParamIds
                          .filter((id) => !scanParamKeys.includes(id))
                          .map((id) => (
                            <MenuItem key={id} value={id}>
                              {id}
                            </MenuItem>
                          ))}
                      </Select>
                    </FormControl>
                  </Grid>
                  <Grid size={{ xs: 4 }}>
                    <TextField
                      size="small"
                      label="Value"
                      type="number"
                      fullWidth
                      value={updateValue}
                      onChange={(e) => setUpdateValue(e.target.value)}
                    />
                  </Grid>
                  <Grid size={{ xs: 3 }}>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={handleUpdateParameter}
                      disabled={!updateParamId || updateValue === ""}
                    >
                      Update
                    </Button>
                  </Grid>
                </Grid>
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
