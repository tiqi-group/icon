import { useMediaQuery, useTheme } from "@mui/material";
import { useMemo } from "react";

/**
 * This hook returns a `gridTemplateColumns` string suitable for a CSS grid layout,
 * based on the current screen size (breakpoint). It uses Material UI's responsive
 * breakpoints to adjust the number of columns depending on the device width.
 *
 * Breakpoint behavior:
 * - xs, sm, md: single-column layout ("repeat(1, 1fr)")
 * - lg and larger: two-column layout ("repeat(2, 1fr)")
 *
 * @returns {string} - A CSS `grid-template-columns` value like "repeat(2, 1fr)"
 */
export const useResponsiveGridColumns = (): string => {
  const theme = useTheme();
  const isXs = useMediaQuery(theme.breakpoints.only("xs"));
  const isSm = useMediaQuery(theme.breakpoints.only("sm"));
  const isMd = useMediaQuery(theme.breakpoints.only("md"));
  const isLg = useMediaQuery(theme.breakpoints.only("lg"));

  return useMemo(() => {
    if (isXs || isSm || isMd) return "repeat(1, 1fr)";
    if (isLg) return "repeat(2, 1fr)";
    return "repeat(2, 1fr)";
  }, [isXs, isSm, isMd, isLg]);
};
