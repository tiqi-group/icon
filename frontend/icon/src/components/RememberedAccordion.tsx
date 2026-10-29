import { Accordion, AccordionProps } from "@mui/material";
import { useSectionCollapsed } from "../hooks/useCollapseState";

interface RememberedAccordionProps extends Omit<
  AccordionProps,
  "expanded" | "defaultExpanded" | "onChange"
> {
  /** Identifies the set of sections, see useCollapseState */
  collapseKey: string;
  /** Identifies this section within the set */
  name: string;
  defaultCollapsed?: boolean;
}

/**
 * Accordion whose collapsed state is remembered. Toggling it re-renders only this
 * accordion, not the page around it.
 */
export const RememberedAccordion = ({
  collapseKey,
  name,
  defaultCollapsed,
  ...props
}: RememberedAccordionProps) => {
  const [collapsed, toggle] = useSectionCollapsed(collapseKey, name, defaultCollapsed);
  return <Accordion {...props} expanded={!collapsed} onChange={toggle} />;
};
