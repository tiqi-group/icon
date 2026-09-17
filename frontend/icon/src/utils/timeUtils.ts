export function hasDayBreak(data: string[]) {
  const first = new Date(data[0]);
  const last = new Date(data.at(-1) || data[0]);
  return !isNaN(first.getDay()) && first.getDay() != last.getDay();
}

const pad = (value: number) => String(value).padStart(2, "0");

export function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  const h = pad(date.getHours());
  const m = pad(date.getMinutes());
  const s = pad(date.getSeconds());
  return `${h}:${m}:${s}`;
}

export function formatDateTime(timestamp: string) {
  const date = new Date(timestamp);
  const year = date.getFullYear();
  // getMonth() is zero-based
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const time = formatTime(timestamp);
  return `${year}-${month}-${day} ${time}`;
}
