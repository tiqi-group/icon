import { useContext } from "react";
import { Link, useSearchParams } from "react-router";
import { Button } from "@mui/material";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import ExperimentDetails from "../components/ExperimentDetails";
import { ExperimentList } from "../components/ExperimentList";
import { experimentDataUrl } from "../utils/dataFilters";

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
          borderRight: "1px solid var(--mui-palette-divider)",
        }}
      >
        <ExperimentList
          experiments={experiments}
          selectedExperiment={selectedExperiment}
          onSelect={handleSelect}
        />
      </div>

      <div style={{ flexGrow: 1, height: "100%", overflow: "auto" }}>
        {selectedExperiment ? (
          <>
            <Button
              component={Link}
              to={experimentDataUrl(selectedExperiment)}
              size="small"
              sx={{ mx: 1, mt: 0.5, textTransform: "none" }}
            >
              View data for this experiment
            </Button>
            <ExperimentDetails experimentKey={selectedExperiment} />
          </>
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
