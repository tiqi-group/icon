import { useContext } from "react";
import { List, ListItemText, Typography, Divider, ListItemButton } from "@mui/material";
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
    <div
      style={{
        display: "flex",
        height: "100vh",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          flexShrink: 0,
          width: "fit-content",
          height: "100%",
          overflowY: "auto",
          backgroundColor: "var(--mui-palette-action-selected)",
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
              <div key={key}>
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
              </div>
            ))}
        </List>
      </div>

      <div style={{ flex: 1, overflowX: "scroll" }}>
        {selectedExperiment ? (
          <ExperimentDetails experimentKey={selectedExperiment} />
        ) : (
          <Typography>
            Select an experiment from the left to view details here.
          </Typography>
        )}
      </div>
    </div>
  );
};

export default ExperimentsPage;
