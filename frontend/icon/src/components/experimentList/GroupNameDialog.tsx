import { useState } from "react";
import {
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  TextField,
} from "@mui/material";
import { validateGroupName } from "../../utils/experimentGroups";

interface GroupNameDialogProps {
  title: string;
  initialName?: string;
  /** Names of the other groups. */
  existingNames: string[];
  onClose: () => void;
  onSubmit: (name: string) => void;
}

export const GroupNameDialog = ({
  title,
  initialName = "",
  existingNames,
  onClose,
  onSubmit,
}: GroupNameDialogProps) => {
  const [name, setName] = useState(initialName);

  const error = validateGroupName(name, existingNames);
  const changed = name.trim() !== initialName;

  // autoFocus on the text field needs disableRestoreFocus
  return (
    <Dialog open onClose={onClose} fullWidth maxWidth="xs" disableRestoreFocus>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (error === null && changed) onSubmit(name.trim());
        }}
      >
        <DialogTitle>{title}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            size="small"
            margin="dense"
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            onFocus={(e) => e.target.select()}
            error={changed && error !== null}
            helperText={(changed && error) || " "}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose}>Cancel</Button>
          <Button type="submit" disabled={error !== null || !changed}>
            OK
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};
