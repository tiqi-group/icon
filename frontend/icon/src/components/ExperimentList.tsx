import { Fragment, useMemo, useState } from "react";
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
import {
  ExperimentContextMenu,
  ExperimentMenuState,
} from "./experimentList/ExperimentContextMenu";
import { GroupContextMenu, GroupMenuState } from "./experimentList/GroupContextMenu";
import { GroupNameDialog } from "./experimentList/GroupNameDialog";
import { getExperimentNameFromExperimentId } from "../utils/experimentUtils";
import {
  DEFAULT_GROUP,
  DEFAULT_GROUP_LABEL,
  ExperimentGroup,
  assignToGroup,
  groupExperiments,
  removeGroup,
  renameGroup,
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
  const [experimentMenu, setExperimentMenu] = useState<ExperimentMenuState | null>(
    null,
  );
  // Experiments waiting for the name of their new group
  const [newGroupExperimentIds, setNewGroupExperimentIds] = useState<string[] | null>(
    null,
  );
  const [groupMenu, setGroupMenu] = useState<GroupMenuState | null>(null);
  const [renamingGroup, setRenamingGroup] = useState<string | null>(null);

  const groups = useMemo(
    () => groupExperiments(Object.keys(experiments), groupsState.assignments),
    [experiments, groupsState.assignments],
  );
  const groupNames = groups
    .map((group) => group.name)
    .filter((name) => name !== DEFAULT_GROUP);
  // The default group gets no heading if it is the only group
  const hasGroups = groupNames.length > 0;

  const renderExperiment = (experimentId: string) => (
    <ListItemButton
      key={experimentId}
      selected={selectedExperiment === experimentId}
      onClick={() => onSelect(experimentId)}
      onContextMenu={(event) => {
        event.preventDefault();
        setExperimentMenu({
          mouseX: event.clientX,
          mouseY: event.clientY,
          experimentIds: [experimentId],
        });
      }}
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
          onContextMenu={
            group.name === DEFAULT_GROUP
              ? undefined
              : (event) => {
                  event.preventDefault();
                  setGroupMenu({
                    mouseX: event.clientX,
                    mouseY: event.clientY,
                    group: group.name,
                  });
                }
          }
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
    <>
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
      <ExperimentContextMenu
        menu={experimentMenu}
        groupNames={groupNames}
        assignments={groupsState.assignments}
        onClose={() => setExperimentMenu(null)}
        onAssign={(group) => {
          const experimentIds = experimentMenu?.experimentIds ?? [];
          updateGroups((state) => assignToGroup(state, experimentIds, group));
          setExperimentMenu(null);
        }}
        onNewGroup={() => {
          setNewGroupExperimentIds(experimentMenu?.experimentIds ?? []);
          setExperimentMenu(null);
        }}
      />
      {newGroupExperimentIds && (
        <GroupNameDialog
          title="New group"
          submitLabel="Create"
          existingNames={groupNames}
          onClose={() => setNewGroupExperimentIds(null)}
          onSubmit={(name) => {
            updateGroups((state) => assignToGroup(state, newGroupExperimentIds, name));
            setNewGroupExperimentIds(null);
          }}
        />
      )}
      <GroupContextMenu
        menu={groupMenu}
        onClose={() => setGroupMenu(null)}
        onRename={() => {
          setRenamingGroup(groupMenu?.group ?? null);
          setGroupMenu(null);
        }}
        onRemove={() => {
          const group = groupMenu?.group;
          if (group !== undefined) updateGroups((state) => removeGroup(state, group));
          setGroupMenu(null);
        }}
      />
      {renamingGroup !== null && (
        <GroupNameDialog
          title="Rename group"
          submitLabel="Rename"
          initialName={renamingGroup}
          existingNames={groupNames.filter((name) => name !== renamingGroup)}
          onClose={() => setRenamingGroup(null)}
          onSubmit={(name) => {
            updateGroups((state) => renameGroup(state, renamingGroup, name));
            setRenamingGroup(null);
          }}
        />
      )}
    </>
  );
};
