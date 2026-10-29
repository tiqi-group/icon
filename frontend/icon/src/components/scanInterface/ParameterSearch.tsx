import SearchIcon from "@mui/icons-material/Search";
import { Autocomplete, TextField, Typography } from "@mui/material";
import { useState } from "react";
import {
  ScanParameterSearchOption,
  makeScannedParamKey,
  searchScanParameterOptions,
} from "../../utils/scanUtils";

const ResultText = ({ primary, secondary }: { primary: string; secondary: string }) => (
  <div>
    <Typography variant="body2">{primary}</Typography>
    <Typography variant="caption" color="text.secondary">
      {secondary}
    </Typography>
  </div>
);

export const ParameterSearch = ({
  options,
  onSelect,
}: {
  options: ScanParameterSearchOption[];
  onSelect: (option: ScanParameterSearchOption) => void;
}) => {
  const [inputValue, setInputValue] = useState("");
  const [open, setOpen] = useState(false);

  return (
    <Autocomplete
      size="small"
      fullWidth
      autoHighlight
      // The icon sits where the dropdowns below have their arrow, but is decoration only.
      forcePopupIcon
      popupIcon={<SearchIcon fontSize="small" />}
      slotProps={{
        // Same elevation as the Select menus, so the popup has the same background.
        paper: { elevation: 8 },
        // About five and a half result rows, so a cut-off row shows there are more.
        listbox: { sx: { maxHeight: 316 } },
        popupIndicator: {
          disableRipple: true,
          sx: { pointerEvents: "none", transform: "none" },
        },
      }}
      // Results only appear while there is something typed.
      open={open && inputValue.trim() !== ""}
      onOpen={() => setOpen(true)}
      onClose={() => setOpen(false)}
      // Always empty after a pick: the dropdowns below show the selection.
      value={null}
      // Typed text survives clicking elsewhere, it is only cleared by a pick.
      clearOnBlur={false}
      inputValue={inputValue}
      onInputChange={(_, value, reason) =>
        setInputValue(reason === "input" ? value : "")
      }
      onChange={(_, option) => {
        if (!option) return;
        onSelect(option);
        setInputValue("");
      }}
      options={options}
      filterOptions={(opts, state) =>
        searchScanParameterOptions(opts, state.inputValue)
      }
      getOptionLabel={(option) => option.displayName}
      getOptionKey={(option) =>
        makeScannedParamKey(
          option.id,
          option.namespace,
          option.deviceNameOrDisplayGroup,
        )
      }
      renderOption={({ key, ...props }, option) => (
        <li key={key} {...props}>
          <ResultText primary={option.displayName} secondary={option.groupLabel} />
        </li>
      )}
      noOptionsText={
        <ResultText primary="No matching parameters" secondary="Try other words" />
      }
      renderInput={(params) => (
        <TextField
          {...params}
          label="Search for parameters"
          placeholder="Type words or parts of words"
          slotProps={{ inputLabel: { ...params.InputLabelProps, shrink: true } }}
        />
      )}
    />
  );
};
