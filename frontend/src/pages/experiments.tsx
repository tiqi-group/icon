import { useContext } from "react";
import { List, ListItemText, ListItemButton, ListSubheader } from "@mui/material";
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
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          flexShrink: 0,
          width: "fit-content",
          height: "100%",
          overflowY: "auto",
          borderRight: "1px solid #ccc",
        }}
      >
        <List
          dense
          disablePadding
          subheader={
            <ListSubheader
              sx={{
                position: "sticky",
                borderBottom: "1px solid #ccc",
              }}
            >
              Experiments
            </ListSubheader>
          }
        >
          {Object.entries(experiments)
            .sort(([keyA], [keyB]) =>
              getExperimentNameFromExperimentId(keyA).localeCompare(
                getExperimentNameFromExperimentId(keyB),
              ),
            )
            .map(([key, metadata]) => (
              <ListItemButton
                key={key}
                selected={selectedExperiment === key}
                onClick={() => handleSelect(key)}
              >
                <ListItemText
                  primary={getExperimentNameFromExperimentId(key)}
                  secondary={metadata.class_name}
                />
              </ListItemButton>
            ))}
        </List>
      </div>

      <div style={{ flexGrow: 1, height: "100%", overflow: "auto" }}>
        {selectedExperiment ? (
          <ExperimentDetails experimentKey={selectedExperiment} />
        ) : (
          <div style={{ padding: 16 }}>
            Select an experiment from the list to view details.
          </div>
        )}
      </div>
    </div>
  );
};

export default ExperimentsPage;
