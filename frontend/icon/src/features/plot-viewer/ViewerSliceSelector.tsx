import { useId, useMemo, useState } from "react";
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

interface ViewerSliceSelectorProps {
  parameterName: string;
  available: number[];
  selected: number[];
  formatValue: (value: number) => string;
  maxSlices: number;
  defaultSlices: number;
  onChange: (values: number[] | null) => void;
}

/** Keep selection details and bulk actions out of the plot's resting toolbar. */
export function ViewerSliceSelector({
  parameterName,
  available,
  selected,
  formatValue,
  maxSlices,
  defaultSlices,
  onChange,
}: ViewerSliceSelectorProps) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const [query, setQuery] = useState("");
  const id = useId();
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const matches = useMemo(() => {
    const search = query.trim().toLowerCase();
    return available.filter((value) =>
      formatValue(value).toLowerCase().includes(search),
    );
  }, [available, formatValue, query]);
  const summary = !selected.length
    ? "None"
    : selected.length === available.length
      ? `All (${available.length})`
      : `${selected.length} of ${available.length}`;
  const close = () => {
    setAnchor(null);
    setQuery("");
  };

  return (
    <>
      <Button
        id={id}
        size="small"
        variant="outlined"
        color="inherit"
        aria-label={`Slices — ${parameterName}: ${summary}`}
        aria-haspopup="dialog"
        aria-expanded={Boolean(anchor)}
        aria-controls={anchor ? `${id}-choices` : undefined}
        endIcon={<ArrowDropDownIcon />}
        onClick={(event) => setAnchor(event.currentTarget)}
        sx={{
          minHeight: 40,
          maxWidth: "100%",
          px: 1.5,
          mb: 1,
          textTransform: "none",
          borderColor: "divider",
          fontWeight: 400,
          gap: 1.5,
          "&:hover": { borderColor: "text.secondary" },
        }}
      >
        <Box
          component="span"
          sx={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
        >
          {parameterName}
        </Box>
        <Box component="span" sx={{ color: "text.secondary", whiteSpace: "nowrap" }}>
          {summary}
        </Box>
      </Button>
      <Popover
        open={Boolean(anchor)}
        anchorEl={anchor}
        onClose={close}
        anchorOrigin={{ vertical: "bottom", horizontal: "left" }}
        transformOrigin={{ vertical: "top", horizontal: "left" }}
        slotProps={{
          paper: { sx: { width: 280, maxWidth: "calc(100vw - 32px)", mt: 0.5 } },
        }}
      >
        <Box id={`${id}-choices`} role="dialog" aria-labelledby={id} sx={{ p: 1 }}>
          <Stack direction="row" spacing={0.5} sx={{ mb: 0.5 }}>
            <Button
              size="small"
              disabled={!available.length || available.length > maxSlices}
              onClick={() => onChange(available)}
              sx={{ textTransform: "none" }}
            >
              All
            </Button>
            <Button
              size="small"
              disabled={!selected.length}
              onClick={() => onChange([])}
              sx={{ textTransform: "none" }}
            >
              None
            </Button>
            {available.length > defaultSlices && (
              <Button
                size="small"
                onClick={() => onChange(null)}
                sx={{ textTransform: "none" }}
              >
                First {defaultSlices}
              </Button>
            )}
          </Stack>
          {available.length > defaultSlices && (
            <TextField
              autoFocus
              fullWidth
              size="small"
              placeholder="Find a value"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              slotProps={{ htmlInput: { "aria-label": "Find a slice value" } }}
              sx={{ mb: 0.5 }}
            />
          )}
          <Box
            role="group"
            aria-label="Slice values"
            sx={{ maxHeight: 280, overflowY: "auto" }}
          >
            {matches.slice(0, 200).map((value, index) => (
              <FormControlLabel
                key={value}
                label={formatValue(value)}
                sx={{
                  display: "flex",
                  m: 0,
                  borderRadius: 1,
                  "&:hover": { bgcolor: "action.hover" },
                }}
                control={
                  <Checkbox
                    size="small"
                    autoFocus={available.length <= defaultSlices && index === 0}
                    checked={selectedSet.has(value)}
                    disabled={selected.length >= maxSlices && !selectedSet.has(value)}
                    onChange={(_, checked) =>
                      onChange(
                        checked
                          ? [...selected, value]
                          : selected.filter((item) => item !== value),
                      )
                    }
                  />
                }
              />
            ))}
            {!matches.length && (
              <Typography variant="body2" color="text.secondary" sx={{ p: 1 }}>
                {available.length ? "No matching values" : "No observed slices yet"}
              </Typography>
            )}
          </Box>
          {(available.length > maxSlices || matches.length > 200) && (
            <Typography
              variant="caption"
              color="text.secondary"
              component="p"
              sx={{ px: 1, pt: 0.5 }}
            >
              {available.length > maxSlices ? `Choose up to ${maxSlices} slices. ` : ""}
              {matches.length > 200
                ? "Showing the first 200 matches; search to narrow."
                : ""}
            </Typography>
          )}
        </Box>
      </Popover>
    </>
  );
}
