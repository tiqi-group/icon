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
  {
    segment: "devices",
    title: "Devices",
    // used https://svg2jsx.com/ to get the code for the svg icon
    icon: (
      <SvgIcon viewBox="0 0 300 319">
        <path d="M158.85 3.25c-3.65 1.3-9.05 4.15-12 6.4-4.35 3.35-6.85 4.4-13.5 5.75C70.4 27.95 17.65 79.85 3.9 142.9-15.1 229.6 54.2 318 141.2 318c54.6 0 90.95-13.05 118.8-42.6 55.85-59.35 52.3-144.65-8.55-205.1L238.2 57.15l5.35-3.55c3.25-2.15 6.35-5.3 8-8.05 3.4-5.8 4.35-5.75 14.35.95 13.95 9.35 15 3.85 1.5-7.85l-2.9-2.55 5.75-5.8c7.45-7.6 8.35-16 1.1-9.95-11.2 9.25-16.75 11.3-17.7 6.55-1.7-8.4-6.85-11.35-34.15-19.5l-19-5.7-17.5-.35c-16.3-.4-17.95-.25-24.15 1.9M218.5 15.5c25.25 7.6 27.5 8.95 27.5 16.1 0 4.75-9.2 10.3-27.95 16.85-27.8 9.65-44.35 11.2-56.05 5.2-3.55-1.85-8.65-4.45-11.2-5.75-11.05-5.6-9.4-24.95 2.85-33.65 6.45-4.55 10.75-5.3 28.85-4.9l17 .35zm-82.35 15.95c-.4 10.7.95 16.2 5.95 24 1.65 2.65 2.85 4.9 2.7 5s-6.35 2.4-13.8 5c-39.45 14-59.85 32.4-73.4 66.25-12.5 31.3-11.5 59.45 3.45 94.3 2.8 6.6 5.6 15.2 6.5 20 3.3 17.4 11.9 33.6 25.9 48.75 7.5 8.1 7.25 8.15-7.1.9-37.55-18.9-63.3-51-75.05-93.65-2.6-9.45-2.55-43.85.1-56C22.9 93.1 62.35 47.45 112 29.55c6.45-2.3 22.5-7.35 24-7.5.3-.05.35 4.2.15 9.4m115.2 49.65c45.7 49 51.65 107.5 16.25 160.75-28.6 43-86 64.75-132.25 50.1-28-8.9-41.55-18.3-49.3-34.15-11.15-22.9-11.6-37.65-1.65-53.2 8.75-13.65 14.2-14.5 54.1-8.15 42.65 6.75 59.5 3.7 77.25-14 4.55-4.5 8.25-7.85 8.25-7.4 0 12.2-15.15 30.95-31.6 39.1l-8.7 4.3-18.7.55c-22.35.6-26.05 2-31.2 11.9-7.1 13.55-2.6 23.1 12.2 25.9 10.8 2.1 15 2.3 23.2 1.2 60.1-8.05 92.45-67.85 67.35-124.5-1.45-3.3-3.75-11.3-5.05-17.8-2.4-12.2-6.55-22.55-12.45-31.1L216 80.15l11.75-4c15.3-5.2 13.8-5.5 23.6 4.95m-38.6 9.75c14 20.75 9.55 50.5-10.4 69.15-12.6 11.8-23.15 14.75-56.85 16.1-41.1 1.6-51.8 4.7-62.45 18.05-5.35 6.7-5.65 6.65-4.1-.35 8.6-37.95 23.6-51.55 59.55-53.9 12-.8 17.1-1.55 20.5-3.05 18.15-7.95 18.95-31.2 1.45-39.75-4.95-2.45-6.1-2.05 22.55-8 27.65-5.8 24.5-6 29.75 1.75M118 95.05c1.95.55 9.6 2.35 17 4 25.9 5.7 34.05 11.85 29.6 22.3-3.35 7.8-7.75 9.55-27.5 10.75-39.1 2.35-55.25 16.95-67.6 61.3-1.85 6.55-2.65 6.4-4.45-.9-6.7-27.7 2.85-58.25 25.45-81.15 15.45-15.65 20.2-18.45 27.5-16.3m117.1 97.1c-8.35 32.85-35.2 55.95-67.95 58.45-16 1.2-28.15-2.5-28.15-8.65 0-9.4 6.35-12.95 25.4-14.1 40.1-2.4 61.55-18.7 68.75-52.4 3-14.1 3.3-14.3 3.65-2.05.2 8.3-.2 12.75-1.7 18.75"></path>
        <path d="M192.9 22.9c-3.1 3.1-3.9 4.6-3.9 7.55 0 15.35 21.1 19.1 25.05 4.4 3.5-13.1-11.55-21.6-21.15-11.95m12.25 4.75c2.25 2.05 2.4 5.65.3 7.8-2.15 2.1-5.05 1.95-7.45-.45-4.85-4.85 2.05-11.95 7.15-7.35"></path>
      </SvgIcon>
    ),
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
