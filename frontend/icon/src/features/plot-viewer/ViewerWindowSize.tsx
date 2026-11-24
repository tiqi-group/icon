import { useState } from "react";
import { TextField } from "@mui/material";

/** Keep edits local until Enter/blur so typing does not reload history repeatedly. */
export function ViewerWindowSize({
  value,
  onChange,
}: {
  value: number;
  onChange: (value: number) => void;
}) {
  const [draft, setDraft] = useState(String(value));
  const [error, setError] = useState(false);
  const apply = () => {
    const next = draft.trim() === "" ? 1000 : Number(draft);
    const valid = Number.isSafeInteger(next) && next >= 1 && next <= 100000;
    setError(!valid);
    if (!valid) return;
    setDraft(String(next));
    if (next !== value) onChange(next);
  };
  return (
    <TextField
      label="Window size"
      type="number"
      size="small"
      value={draft}
      onChange={(event) => {
        setDraft(event.target.value);
        setError(false);
      }}
      onBlur={apply}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          apply();
        }
      }}
      error={error}
      helperText={error ? "Enter a whole number from 1 to 100,000." : undefined}
      title="Show the last N points. Press Enter or leave the field to apply. Clear to reset to 1,000."
      slotProps={{ htmlInput: { min: 1, max: 100000, step: 1 } }}
      sx={{ width: 150 }}
    />
  );
}
