import React, { useContext } from "react";
import {
  Box,
  List,
  ListItemText,
  Typography,
  Divider,
  ListItemButton,
} from "@mui/material";
import { useSearchParams } from "react-router";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import ExperimentDetails from "../components/ExperimentDetails";

function getExperimentNameFromExperimentId(experimentId: string): string {
  const match = experimentId.match(/\((.*?)\)/);
  return match ? match[1] : experimentId;
}

const ExperimentsPage = () => {
  const experiments = useContext(ExperimentsContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedExperiment = searchParams.get("experiment") || "";

  const handleSelect = (experimentId: string) => {
    setSearchParams({ experiment: experimentId });
  };

  return (
    <Box
      display="flex"
      height="100vh"
      overflow="hidden"
      border={1}
      borderColor="action.focus"
    >
      <Box
        sx={{
          flexShrink: 0,
          width: "fit-content",
          height: "100%",
          overflowY: "auto",
          bgcolor: "action.selected",
          borderRight: 1,
          borderColor: "action.focus",
        }}
      >
        <List dense sx={{ pt: 0 }}>
          {Object.entries(experiments)
            .sort(([keyA], [keyB]) =>
              getExperimentNameFromExperimentId(keyA).localeCompare(
                getExperimentNameFromExperimentId(keyB),
              ),
            )
            .map(([key, metadata], index) => (
              <React.Fragment key={key}>
                <ListItemButton
                  selected={selectedExperiment === key}
                  onClick={() => handleSelect(key)}
                >
                  <ListItemText
                    primary={getExperimentNameFromExperimentId(key)}
                    secondary={metadata.class_name}
                  />
                </ListItemButton>
                {index < Object.keys(experiments).length - 1 && <Divider />}
              </React.Fragment>
            ))}
        </List>
      </Box>

      <Box sx={{ flex: 1, overflowX: "scroll" }}>
        {selectedExperiment ? (
          <ExperimentDetails experimentKey={selectedExperiment} />
        ) : (
          <Typography>
            Select an experiment from the left to view details here.
          </Typography>
        )}
      </Box>
    </Box>
  );
};

export default ExperimentsPage;
