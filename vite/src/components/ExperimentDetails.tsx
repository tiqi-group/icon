import React, { useContext, useState } from "react";
import {
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Menu,
  MenuItem,
  useMediaQuery,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import { NumberComponent } from "./NumberComponent";
import { useTheme } from "@mui/material/styles";

const ExperimentDetails = ({ experimentKey }: { experimentKey: string }) => {
  const experiments = useContext(ExperimentsContext);
  const experiment = experiments[experimentKey];
  const [menuAnchor, setMenuAnchor] = useState<{
    mouseX: number | null;
    mouseY: number | null;
  }>({
    mouseX: null,
    mouseY: null,
  });
  const theme = useTheme();

  const isXs = useMediaQuery(theme.breakpoints.only("xs"));
  const isSm = useMediaQuery(theme.breakpoints.only("sm"));
  const isMd = useMediaQuery(theme.breakpoints.only("md"));
  const isLg = useMediaQuery(theme.breakpoints.only("lg"));

  const getGridTemplateColumns = () => {
    if (isXs) return "repeat(1, 1fr)";
    if (isSm) return "repeat(1, 1fr)";
    if (isMd) return "repeat(2, 1fr)";
    if (isLg) return "repeat(3, 1fr)";
    return "repeat(4, 1fr)"; // xl and larger
  };

  const handleRightClick = (event: React.MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    setMenuAnchor({
      mouseX: event.clientX,
      mouseY: event.clientY,
    });
  };

  const handleCloseMenu = () => {
    setMenuAnchor({ mouseX: null, mouseY: null });
  };

  if (!experiment) {
    return (
      <Typography>Select an experiment from the left to view details here.</Typography>
    );
  }

  return (
    <Box sx={{ flex: 1, p: 3, overflowY: "auto" }}>
      <Typography variant="h5" component="h2" gutterBottom>
        {experiment.constructor_kwargs.name} Experiment
      </Typography>

      {Object.entries(experiment.parameters).map(([group, parameters]) => (
        <Accordion key={experimentKey + group} defaultExpanded>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h6">{group}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <Box
              sx={{
                display: "grid",
                rowGap: 1,
                columnGap: 4,
                gridTemplateColumns: getGridTemplateColumns(),
              }}
            >
              {Object.entries(parameters).map(([paramId, paramData]) => (
                <NumberComponent
                  key={paramId}
                  type={paramData.unit ? "Quantity" : "float"}
                  fullAccessPath={paramId}
                  value={paramData.default_value}
                  readOnly={false}
                  docString={paramData.display_name}
                  isInstantUpdate={true}
                  unit={paramData.unit}
                  addNotification={(msg) => console.log(msg)}
                  changeCallback={(updatedValue) => console.log(updatedValue)}
                  displayName={paramData.display_name}
                  id={paramId}
                  onContextMenu={handleRightClick}
                />
              ))}
            </Box>
          </AccordionDetails>
        </Accordion>
      ))}

      <Menu
        open={menuAnchor.mouseY !== null}
        onClose={handleCloseMenu}
        anchorReference="anchorPosition"
        anchorPosition={
          menuAnchor.mouseY !== null && menuAnchor.mouseX !== null
            ? { top: menuAnchor.mouseY, left: menuAnchor.mouseX }
            : undefined
        }
      >
        <MenuItem
          onClick={() => {
            handleCloseMenu();
            console.log("Option 1 clicked");
          }}
        >
          Scan Variable
        </MenuItem>
      </Menu>
    </Box>
  );
};

export default ExperimentDetails;
