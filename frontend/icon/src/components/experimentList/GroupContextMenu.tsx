import { Menu, MenuItem } from "@mui/material";

export interface GroupMenuState {
  mouseX: number;
  mouseY: number;
  group: string;
}

interface GroupContextMenuProps {
  menu: GroupMenuState | null;
  onClose: () => void;
  onRename: () => void;
  onRemove: () => void;
}

export const GroupContextMenu = ({
  menu,
  onClose,
  onRename,
  onRemove,
}: GroupContextMenuProps) => (
  <Menu
    open={menu !== null}
    onClose={onClose}
    anchorReference="anchorPosition"
    anchorPosition={menu ? { top: menu.mouseY, left: menu.mouseX } : undefined}
    transitionDuration={0}
  >
    <MenuItem onClick={onRename}>Rename group...</MenuItem>
    <MenuItem onClick={onRemove}>Remove group</MenuItem>
  </Menu>
);
