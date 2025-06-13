import DashboardIcon from "@mui/icons-material/Dashboard";
import ScienceIcon from "@mui/icons-material/Science";
import TimelineIcon from "@mui/icons-material/Timeline";
import { Outlet } from "react-router";
import { ReactRouterAppProvider } from "@toolpad/core/react-router";
import type { Navigation } from "@toolpad/core/AppProvider";
import { useEffect, useReducer, useRef, useState } from "react";
import { runMethod, socket } from "./socket";
import { deserialize } from "./utils/deserializer";
import { SerializedObject } from "./types/SerializedObject";
import { ExperimentsContext } from "./contexts/ExperimentsContext";
import {
  ExperimentDict,
  ParameterMetadata,
  ParameterValueType,
} from "./types/ExperimentMetadata";
import { SvgIcon } from "@mui/material";
import { ParameterMetadataContext } from "./contexts/ParameterMetadataContext";
import { ParameterDisplayGroupsContext } from "./contexts/ParameterDisplayGroupsContext";
import { ScanProvider } from "./contexts/ScanContext";
import { reducer, JobsContext } from "./contexts/JobsContext";
import { ParameterStoreProvider } from "./contexts/ParameterStoreContext";
import { useJobsSync } from "./hooks/useJobsSync";
import { createParameterStore } from "./stores/parmeterStore";

interface ParameterUpdate {
  id: string;
  value: ParameterValueType;
}

const NAVIGATION: Navigation = [
  {
    kind: "header",
    title: "Main items",
  },
  {
    title: "Start",
    icon: <DashboardIcon />,
  },
  {
    segment: "parameters",
    title: "Parameters",
    // used https://nikitahl.github.io/svg-2-code/ to get the code for the svg icon
    icon: (
      <SvgIcon viewBox="0 0 32 32">
        <path d="M29.000,13.858 L29.000,31.000 C29.000,31.553 28.553,32.000 28.000,32.000 C27.447,32.000 27.000,31.553 27.000,31.000 L27.000,13.858 C25.279,13.411 24.000,11.859 24.000,10.000 C24.000,8.141 25.279,6.589 27.000,6.142 L27.000,1.000 C27.000,0.447 27.447,0.000 28.000,0.000 C28.553,0.000 29.000,0.447 29.000,1.000 L29.000,6.142 C30.721,6.589 32.000,8.141 32.000,10.000 C32.000,11.859 30.721,13.411 29.000,13.858 ZM28.000,8.000 C26.898,8.000 26.000,8.897 26.000,10.000 C26.000,11.103 26.898,12.000 28.000,12.000 C29.103,12.000 30.000,11.103 30.000,10.000 C30.000,8.897 29.103,8.000 28.000,8.000 ZM17.000,25.858 L17.000,31.000 C17.000,31.553 16.553,32.000 16.000,32.000 C15.447,32.000 15.000,31.553 15.000,31.000 L15.000,25.858 C13.279,25.411 12.000,23.859 12.000,22.000 C12.000,20.141 13.279,18.589 15.000,18.142 L15.000,1.000 C15.000,0.447 15.447,0.000 16.000,0.000 C16.553,0.000 17.000,0.447 17.000,1.000 L17.000,18.142 C18.721,18.589 20.000,20.141 20.000,22.000 C20.000,23.859 18.721,25.411 17.000,25.858 ZM16.000,20.000 C14.897,20.000 14.000,20.898 14.000,22.000 C14.000,23.102 14.897,24.000 16.000,24.000 C17.103,24.000 18.000,23.102 18.000,22.000 C18.000,20.898 17.103,20.000 16.000,20.000 ZM5.000,19.858 L5.000,31.000 C5.000,31.553 4.553,32.000 4.000,32.000 C3.447,32.000 3.000,31.553 3.000,31.000 L3.000,19.858 C1.279,19.411 0.000,17.859 0.000,16.000 C0.000,14.141 1.279,12.589 3.000,12.142 L3.000,1.000 C3.000,0.447 3.447,0.000 4.000,0.000 C4.553,0.000 5.000,0.447 5.000,1.000 L5.000,12.142 C6.721,12.589 8.000,14.141 8.000,16.000 C8.000,17.859 6.721,19.411 5.000,19.858 ZM4.000,14.000 C2.898,14.000 2.000,14.898 2.000,16.000 C2.000,17.103 2.898,18.000 4.000,18.000 C5.102,18.000 6.000,17.103 6.000,16.000 C6.000,14.898 5.102,14.000 4.000,14.000 Z" />
      </SvgIcon>
    ),
  },
  {
    segment: "experiments",
    title: "Experiments",
    icon: <ScienceIcon />,
  },
  {
    segment: "data",
    title: "Data",
    icon: <TimelineIcon />,
  },
];

const BRANDING = {
  title: "ICON",
};

const createNamespaceGroups = (
  parameterMetadata: Record<string, Record<string, ParameterMetadata>>,
) => {
  const namespaceGroups: Record<string, string[]> = {};

  // Group display groups by namespace
  Object.keys(parameterMetadata).forEach((key) => {
    const [namespace, groupName] = key.split(" (");
    const cleanGroupName = groupName.replace(")", "");

    if (!namespaceGroups[namespace]) {
      namespaceGroups[namespace] = [];
    }

    namespaceGroups[namespace].push(cleanGroupName);
  });

  // Sort display groups for each namespace
  Object.keys(namespaceGroups).forEach((namespace) => {
    namespaceGroups[namespace].sort();
  });

  // Sort namespaces alphabetically and return a sorted object
  return Object.fromEntries(
    Object.entries(namespaceGroups).sort(([a], [b]) => a.localeCompare(b)),
  );
};

export default function App() {
  const [experiments, setExperiments] = useState<ExperimentDict>({});
  const [parameterDisplayGroups, setParameterDisplayGroups] = useState<
    [Record<string, Record<string, ParameterMetadata>>, Record<string, string[]>]
  >([{}, {}]);
  const [parameterMetadata, setParameterMetadata] = useState<
    Record<string, ParameterMetadata>
  >({});
  const [scheduledJobs, schedulerDispatch] = useReducer(reducer, {});
  const parameterStore = useRef(createParameterStore()).current;

  useJobsSync(schedulerDispatch);
  useEffect(() => {
    socket.on("parameter.update", ({ id, value }: ParameterUpdate) => {
      parameterStore.set(id, value);
    });

    runMethod("parameters.get_all_parameters", [], {}, (ack) => {
      const parameterMapping = deserialize(ack as SerializedObject) as Record<
        string,
        ParameterValueType
      >;
      console.log(
        parameterMapping[
          "namespace='experiment_library.experiments.ramsey_experiment.RamseyExperiment.Ramsey 2' parameter_group='Local detection settings' param_type='ParameterTypes.BOOLEAN' description='729 state prep'"
        ],
      );
      parameterStore.bulkSet(parameterMapping);
    });

    // Fetch experiments
    runMethod("experiments.get_experiments", [], {}, (ack) => {
      setExperiments(deserialize(ack as SerializedObject) as ExperimentDict);
    });

    runMethod("parameters.get_parameter_metadata", [], {}, (ack) => {
      const parameterMetadata = deserialize(ack as SerializedObject) as Record<
        string,
        ParameterMetadata
      >;
      setParameterMetadata(parameterMetadata);
    });

    runMethod("parameters.get_display_groups", [], {}, (ack) => {
      const parameterDisplayGroups = deserialize(ack as SerializedObject) as Record<
        string,
        Record<string, ParameterMetadata>
      >;
      setParameterDisplayGroups([
        parameterDisplayGroups,
        createNamespaceGroups(parameterDisplayGroups),
      ]);
    });

    return () => {
      socket.off("parameter.update");
    };
  }, []);

  return (
    <ReactRouterAppProvider navigation={NAVIGATION} branding={BRANDING}>
      <ParameterStoreProvider store={parameterStore}>
        <ScanProvider>
          <JobsContext.Provider value={scheduledJobs}>
            <ParameterMetadataContext.Provider value={parameterMetadata}>
              <ParameterDisplayGroupsContext.Provider value={parameterDisplayGroups}>
                <ExperimentsContext.Provider value={experiments}>
                  <Outlet />
                </ExperimentsContext.Provider>
              </ParameterDisplayGroupsContext.Provider>
            </ParameterMetadataContext.Provider>
          </JobsContext.Provider>
        </ScanProvider>
      </ParameterStoreProvider>
    </ReactRouterAppProvider>
  );
}
