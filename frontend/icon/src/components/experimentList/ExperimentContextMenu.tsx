import { Divider, ListSubheader, Menu, MenuItem } from "@mui/material";
import { DEFAULT_GROUP } from "../../utils/experimentGroups";

export interface ExperimentMenuState {
  mouseX: number;
  mouseY: number;
  experimentIds: string[];
}

interface ExperimentContextMenuProps {
  menu: ExperimentMenuState | null;
  groupNames: string[];
  assignments: Record<string, string>;
  onClose: () => void;
  onAssign: (group: string) => void;
  onNewGroup: () => void;
}

export const ExperimentContextMenu = ({
  menu,
  groupNames,
  assignments,
  onClose,
  onAssign,
  onNewGroup,
}: ExperimentContextMenuProps) => {
  const currentGroups = new Set(
    (menu?.experimentIds ?? []).map((id) => assignments[id] ?? DEFAULT_GROUP),
  );
  // A group that already holds all of the experiments is not offered
  const isCurrent = (group: string) =>
    currentGroups.size === 1 && currentGroups.has(group);
  const targetGroups = groupNames.filter((name) => !isCurrent(name));

  return (
    <Menu
      open={menu !== null}
      onClose={onClose}
      anchorReference="anchorPosition"
      anchorPosition={menu ? { top: menu.mouseY, left: menu.mouseX } : undefined}
      transitionDuration={0}
    >
      {targetGroups.length > 0 && (
        <ListSubheader sx={{ lineHeight: "32px" }}>Add to group</ListSubheader>
      )}
      {targetGroups.map((name) => (
        <MenuItem key={name} onClick={() => onAssign(name)}>
          {name}
        </MenuItem>
      ))}
      {targetGroups.length > 0 && <Divider />}
      <MenuItem onClick={onNewGroup}>Add to new group...</MenuItem>
      <MenuItem
        disabled={isCurrent(DEFAULT_GROUP)}
        onClick={() => onAssign(DEFAULT_GROUP)}
      >
        Remove from group
      </MenuItem>
    </Menu>
  );
};
