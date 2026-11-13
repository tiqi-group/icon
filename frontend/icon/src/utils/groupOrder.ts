/**
 * Order of named groups that stays the same when groups are added: groups not seen
 * before go on top, in their incoming order, followed by the known ones in the
 * remembered order.
 *
 * @param remembered Group names in the order they were shown before, including ones
 *   that no longer exist, so that a group that is missing for a while comes back at
 *   its old place
 * @param current The group names as they come in now, in any order
 * @returns The order to show `current` in, and the order to remember
 */
export const mergeGroupOrder = (
  remembered: string[],
  current: string[],
): { shown: string[]; remembered: string[] } => {
  const known = new Set(remembered);
  const added = current.filter((name) => !known.has(name));
  const present = new Set(current);
  return {
    shown: [...added, ...remembered.filter((name) => present.has(name))],
    remembered: [...added, ...remembered],
  };
};

export const parseGroupOrder = (raw: string | null): string[] => {
  try {
    const parsed: unknown = JSON.parse(raw ?? "[]");
    if (Array.isArray(parsed)) return parsed.filter((name) => typeof name === "string");
  } catch {
    // fall through
  }
  return [];
};
