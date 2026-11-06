import { Accordion, AccordionProps } from "@mui/material";
import { useStoredFlag } from "../hooks/useStoredFlags";

interface RememberedAccordionProps extends Omit<
  AccordionProps,
  "expanded" | "defaultExpanded" | "onChange"
> {
  /** localStorage key of the set of expanded sections, see useStoredFlags */
  storageKey: string;
  /** Identifies this section within the set */
  name: string;
}

/**
 * Accordion that starts collapsed and remembers whether it is expanded. Toggling it
 * re-renders only this accordion, not the page around it.
 */
export const RememberedAccordion = ({
  storageKey,
  name,
  ...props
}: RememberedAccordionProps) => {
  const [expanded, setExpanded] = useStoredFlag(storageKey, name);
  return (
    <Accordion
      {...props}
      expanded={expanded}
      onChange={(_, value) => setExpanded(value)}
    />
  );
};
