import { useContext } from "react";
import { List, ListItemText, ListItemButton, ListSubheader } from "@mui/material";
import { useSearchParams } from "react-router";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import ExperimentDetails from "../components/ExperimentDetails";
import { ScanProvider } from "../contexts/ScanProvider";
import { getExperimentNameFromExperimentId } from "../utils/experimentUtils";

const ExperimentsPage = () => {
  const experiments = useContext(ExperimentsContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedExperiment = searchParams.get("experiment") || "";

  const handleSelect = (experimentId: string) => {
    setSearchParams({ experiment: experimentId });
  };

  return (
    <ScanProvider experimentId={selectedExperiment}>
      <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
        <div
          style={{
            flexShrink: 0,
            width: "fit-content",
            height: "100%",
            overflowY: "auto",
            borderRight: "1px solid var(--mui-palette-divider)",
          }}
        >
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
    </ScanProvider>
  );
};

export default ExperimentsPage;
