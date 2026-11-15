import { useId, useState } from "react";
import {
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Popover,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import ArrowDropDownIcon from "@mui/icons-material/ArrowDropDown";
import { getExperimentNameFromExperimentId } from "../../utils/experimentUtils";

interface ExperimentFilterPickerProps {
  options: string[];
  selection: string[] | null;
  onChange: (selection: string[] | null) => void;
}

export function ExperimentFilterPicker({
  options,
  selection,
  onChange,
}: ExperimentFilterPickerProps) {
  const id = useId();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [query, setQuery] = useState("");
  const selected = new Set(selection ?? options);
  const search = query.trim().toLowerCase();
  const matches = options.filter((option) => option.toLowerCase().includes(search));
  const summary =
    selection === null
      ? "All"
      : selected.size === 0
        ? "None"
        : `${selected.size} of ${options.length}`;

  return (
    <>
      <Button
        id={id}
        type="button"
        size="small"
        variant="outlined"
        color="inherit"
        aria-label={`Experiments: ${summary}`}
        aria-haspopup="dialog"
        aria-expanded={Boolean(anchor)}
        aria-controls={anchor ? `${id}-choices` : undefined}
        endIcon={<ArrowDropDownIcon />}
        onClick={(event) => setAnchor(event.currentTarget)}
        sx={{
          minHeight: 40,
          justifyContent: "space-between",
          textTransform: "none",
          borderColor: "divider",
          fontWeight: 400,
        }}
      >
        Experiments
        <Box component="span" sx={{ ml: "auto", color: "text.secondary" }}>
          {summary}
        </Box>
      </Button>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={() => {
          setAnchor(null);
          setQuery("");
        }}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        slotProps={{
          paper: { sx: { width: 300, maxWidth: "calc(100vw - 32px)", mt: 0.5 } },
        }}
      >
        <Box id={`${id}-choices`} role="dialog" aria-labelledby={id} sx={{ p: 1 }}>
          <Stack direction="row" spacing={0.5} sx={{ mb: 0.5 }}>
            <Button
              type="button"
              size="small"
              onClick={() => onChange(null)}
              sx={{ textTransform: "none" }}
            >
              All
            </Button>
            <Button
              type="button"
              size="small"
              onClick={() => onChange([])}
              sx={{ textTransform: "none" }}
            >
              None
            </Button>
          </Stack>
          <TextField
            autoFocus
            fullWidth
            size="small"
            placeholder="Find an experiment"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            slotProps={{ htmlInput: { "aria-label": "Find an experiment" } }}
            sx={{ mb: 0.5 }}
          />
          <Box
            role="group"
            aria-label="Experiments"
            sx={{ maxHeight: 280, overflowY: "auto" }}
          >
            {matches.map((option) => (
              <FormControlLabel
                key={option}
                title={option}
                label={getExperimentNameFromExperimentId(option)}
                sx={{
                  display: "flex",
                  m: 0,
                  borderRadius: 1,
                  overflowWrap: "anywhere",
                  "&:hover": { bgcolor: "action.hover" },
                }}
                control={
                  <Checkbox
                    size="small"
                    checked={selected.has(option)}
                    onChange={(_, checked) => {
                      const next = new Set(selected);
                      if (checked) next.add(option);
                      else next.delete(option);
                      onChange(
                        next.size === options.length
                          ? null
                          : options.filter((id) => next.has(id)),
                      );
                    }}
                  />
                }
              />
            ))}
            {matches.length === 0 && (
              <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
                {options.length
                  ? "No matching experiments"
                  : "No experiments available"}
              </Typography>
            )}
          </Box>
        </Box>
      </Popover>
    </>
  );
}
