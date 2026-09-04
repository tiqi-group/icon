export const numberValid = (val: string, minValue: number, maxValue: number) => {
  const parsed = Number.parseFloat(val);
  return !isNaN(+val) && !isNaN(parsed) && parsed >= minValue && parsed <= maxValue;
};
