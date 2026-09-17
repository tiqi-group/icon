import { Fragment, useMemo } from "react";
import {
  Collapse,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  ListSubheader,
} from "@mui/material";
import { ChevronRight, ExpandMore } from "@mui/icons-material";
import { ExperimentDict } from "../types/ExperimentMetadata";
import { useExperimentGroups } from "../hooks/useExperimentGroups";
import { getExperimentNameFromExperimentId } from "../utils/experimentUtils";
import {
  DEFAULT_GROUP,
  DEFAULT_GROUP_LABEL,
  ExperimentGroup,
  groupExperiments,
  toggleCollapsed,
} from "../utils/experimentGroups";

interface ExperimentListProps {
  experiments: ExperimentDict;
  selectedExperiment: string;
  onSelect: (experimentId: string) => void;
}

export const ExperimentList = ({
  experiments,
  selectedExperiment,
  onSelect,
}: ExperimentListProps) => {
  const [groupsState, updateGroups] = useExperimentGroups();

  const groups = useMemo(
    () => groupExperiments(Object.keys(experiments), groupsState.assignments),
    [experiments, groupsState.assignments],
  );
  // The default group gets no heading if it is the only group
  const hasGroups = groups.some((group) => group.name !== DEFAULT_GROUP);

  const renderExperiment = (experimentId: string) => (
    <ListItemButton
      key={experimentId}
      selected={selectedExperiment === experimentId}
      onClick={() => onSelect(experimentId)}
      sx={hasGroups ? { pl: 5.5 } : undefined}
    >
      <ListItemText
        primary={getExperimentNameFromExperimentId(experimentId)}
        secondary={experiments[experimentId].class_name}
      />
    </ListItemButton>
  );

  const renderGroup = (group: ExperimentGroup) => {
    const collapsed = groupsState.collapsed.includes(group.name);
    return (
      <Fragment key={group.name}>
        <ListItemButton
          onClick={() => updateGroups((state) => toggleCollapsed(state, group.name))}
        >
          <ListItemIcon sx={{ minWidth: 28 }}>
            {collapsed ? (
              <ChevronRight fontSize="small" />
            ) : (
              <ExpandMore fontSize="small" />
            )}
          </ListItemIcon>
          <ListItemText
            primary={group.name === DEFAULT_GROUP ? DEFAULT_GROUP_LABEL : group.name}
          />
        </ListItemButton>
        <Collapse in={!collapsed}>
          <List dense disablePadding>
            {group.experimentIds.map(renderExperiment)}
          </List>
        </Collapse>
      </Fragment>
    );
  };

  return (
    <List
      dense
      disablePadding
      subheader={
        <ListSubheader
          sx={{
            position: "sticky",
            borderBottom: "1px solid var(--mui-palette-divider)",
          }}
        >
          Experiments
        </ListSubheader>
      }
    >
      {hasGroups
        ? groups.map(renderGroup)
        : groups.flatMap((group) => group.experimentIds).map(renderExperiment)}
    </List>
  );
};
