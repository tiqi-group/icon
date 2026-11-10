import { useEffect, useState } from "react";
import { Alert, Stack, TextField } from "@mui/material";
import type { ViewerBounds } from "./viewerAxisBounds";

type InputType = "number" | "datetime-local" | null;
const keys = ["xMin", "xMax", "yMin", "yMax"] as const;
const labels = { xMin: "X min", xMax: "X max", yMin: "Y min", yMax: "Y max" };
function format(value: number | null, type: InputType) {
  if (value === null) return "";
  if (type !== "datetime-local") return String(value);
  const date = new Date(value);
  return new Date(value - date.getTimezoneOffset() * 60000).toISOString().slice(0, 23);
}
export function ViewerAxisLimits({
  value,
  xType,
  yType,
  onApply,
}: {
  value: ViewerBounds;
  xType: InputType;
  yType: InputType;
  onApply: (value: ViewerBounds) => string | null;
}) {
  const formatted = () =>
    Object.fromEntries(
      keys.map((key) => [key, format(value[key], key[0] === "x" ? xType : yType)]),
    ) as Record<keyof ViewerBounds, string>;
  const [draft, setDraft] = useState(formatted);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setDraft(formatted());
    setError(null);
  }, [value, xType, yType]);
  const apply = () => {
    const next = Object.fromEntries(
      keys.map((key) => {
        const type = key[0] === "x" ? xType : yType;
        return [
          key,
          draft[key].trim() === ""
            ? null
            : type === "datetime-local"
              ? new Date(draft[key]).getTime()
              : Number(draft[key]),
        ];
      }),
    ) as unknown as ViewerBounds;
    setError(onApply(next));
  };
  return (
    <Stack spacing={0.5} sx={{ px: 1, pb: 1 }}>
      <Stack direction="row" gap={1} flexWrap="wrap">
        {keys.map((key) => {
          const type = key[0] === "x" ? xType : yType;
          return (
            <TextField
              key={key}
              label={labels[key]}
              type={type ?? "number"}
              size="small"
              value={draft[key]}
              disabled={!type}
              placeholder="Auto"
              title="Enter or leave the field to apply. Clear for Auto. X limits hold the current view."
              onChange={(event) => {
                setDraft((previous) => ({ ...previous, [key]: event.target.value }));
                setError(null);
              }}
              onBlur={apply}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  apply();
                }
              }}
              slotProps={{ inputLabel: { shrink: true }, htmlInput: { step: "any" } }}
              sx={{ width: type === "datetime-local" ? 240 : 130 }}
            />
          );
        })}
      </Stack>
      {error && (
        <Alert severity="warning" sx={{ py: 0 }}>
          {error}
        </Alert>
      )}
    </Stack>
  );
}
