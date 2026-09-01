function decimalsToRepresent(n: number): number {
  if (!Number.isFinite(n)) return 0;
  for (let d = 0; d <= 12; d++) {
    if (Math.abs(Number(n.toFixed(d)) - n) < Math.max(1e-12, Math.abs(n) * 1e-10)) {
      return d;
    }
  }
  return 12;
}

export function xDecimalsFromValues(values: number[]): number {
  const nums = values.filter(Number.isFinite);
  if (nums.length === 0) return 0;
  return Math.max(...nums.map(decimalsToRepresent));
}

export function formatNum(value: unknown, decimals: number): string {
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return String(value ?? "");
  return Number(num.toFixed(decimals)).toString();
}
