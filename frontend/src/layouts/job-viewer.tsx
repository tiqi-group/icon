import { Outlet } from "react-router";
import { ReactRouterAppProvider } from "@toolpad/core/react-router";
import { BRANDING } from "../App";
import { ParameterStoreProvider } from "../contexts/ParameterStoreContext";
import { createParameterStore } from "../stores/parmeterStore";
import { useEffect, useRef } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";
import { ParameterValueType } from "../types/ExperimentMetadata";

interface ParameterUpdate {
  id: string;
  value: ParameterValueType;
}

export default function JobViewerLayout() {
  const parameterStore = useRef(createParameterStore()).current;

  useEffect(() => {
    socket.on("parameter.update", ({ id, value }: ParameterUpdate) => {
      parameterStore.set(id, value);
    });

    runMethod("parameters.get_all_parameters", [], {}, (ack) => {
      const parameterMapping = deserialize(ack as SerializedObject) as Record<
        string,
        ParameterValueType
      >;
      parameterStore.bulkSet(parameterMapping);
    });

    return () => {
      socket.off("parameter.update");
    };
  }, []);
  return (
    <ReactRouterAppProvider branding={BRANDING}>
      <ParameterStoreProvider store={parameterStore}>
        <Outlet />
      </ParameterStoreProvider>
    </ReactRouterAppProvider>
  );
}
