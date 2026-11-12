import { useContext } from "react";
import { useSearchParams } from "react-router";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import ExperimentDetails from "../components/ExperimentDetails";
import { ExperimentList } from "../components/ExperimentList";

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
