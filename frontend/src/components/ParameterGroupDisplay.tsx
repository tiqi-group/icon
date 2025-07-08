import { useMediaQuery } from "@mui/material";
import { useTheme } from "@mui/material/styles";
import { useContext, useMemo } from "react";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import { ParameterDisplayGroupsContext } from "../contexts/ParameterDisplayGroupsContext";
import { ButtonComponent } from "./parameterComponents/Button";
import { ParameterNumberComponent } from "./parameterComponents/ParameterNumberComponent";
import { Combobox } from "./parameterComponents/Combobox";
import { useScanContext } from "../hooks/useScanContext";
import { getScanIndex } from "../utils/getScanIndex";

interface ParameterGroupDisplayProps {
  experimentKey?: string;
  experimentGroup?: string;
  namespace?: string;
  displayGroup?: string;
}

const extractNamespaceFromParamId = (parameterId: string): string | null => {
  const match = parameterId.match(/namespace='([^']+)'/);
  return match ? match[1] : null;
};

export const ParameterGroupDisplay = ({
  experimentKey,
  experimentGroup,
  namespace,
  displayGroup,
}: ParameterGroupDisplayProps) => {
  const theme = useTheme();
  const isXs = useMediaQuery(theme.breakpoints.only("xs"));
  const isSm = useMediaQuery(theme.breakpoints.only("sm"));
  const isMd = useMediaQuery(theme.breakpoints.only("md"));
  const isLg = useMediaQuery(theme.breakpoints.only("lg"));
  const { scannedParamKeys } = useScanContext();

  const gridTemplateColumns = useMemo(() => {
    if (isXs || isSm || isMd) return "repeat(1, 1fr)";
    if (isLg) return "repeat(2, 1fr)";
    return "repeat(2, 1fr)"; // xl and larger
  }, [isXs, isSm, isMd, isLg]);

  const experiments = useContext(ExperimentsContext);
  const [parameterDisplayGroups] = useContext(ParameterDisplayGroupsContext);

  // Determine parameters based on props
  const parameters = useMemo(() => {
    if (experimentKey && experimentGroup) {
      // Fetch parameters from ExperimentsContext
      return experiments[experimentKey]?.parameters?.[experimentGroup] || {};
    }
    if (namespace && displayGroup) {
      // Fetch parameters from ParameterDisplayGroupsContext
      return parameterDisplayGroups[`${namespace} (${displayGroup})`] || {};
    }
    return {};
  }, [
    experimentKey,
    experimentGroup,
    namespace,
    displayGroup,
    experiments,
    parameterDisplayGroups,
  ]);

  // Memoize sorting
  const sortedParameters = useMemo(() => {
    return Object.entries(parameters).sort((a, b) =>
      a[1].display_name.localeCompare(b[1].display_name),
    );
  }, [parameters]);

  return (
    <div
      style={{
        display: "grid",
        rowGap: 8,
        columnGap: 24,
        gridTemplateColumns,
      }}
    >
      {sortedParameters.map(([paramId]) => {
        const scanIndex = getScanIndex(paramId, scannedParamKeys);

        if (paramId.includes("param_type='ParameterTypes.BOOLEAN'")) {
          return (
            <ButtonComponent
              scanIndex={scanIndex}
              key={paramId}
              id={paramId}
              namespace={
                namespace === undefined
                  ? experimentKey === undefined
                    ? ""
                    : extractNamespaceFromParamId(paramId)!
                  : namespace
              }
              displayGroup={
                displayGroup === undefined
                  ? experimentGroup === undefined
                    ? ""
                    : experimentGroup
                  : displayGroup
              }
            />
          );
        } else if (paramId.includes("param_type='ParameterTypes.ENUM'")) {
          return <Combobox key={paramId} id={paramId} />;
        } else {
          return (
            <ParameterNumberComponent
              scanIndex={scanIndex}
              key={paramId}
              id={paramId}
              namespace={
                namespace === undefined
                  ? experimentKey === undefined
                    ? ""
                    : extractNamespaceFromParamId(paramId)!
                  : namespace
              }
              displayGroup={
                displayGroup === undefined
                  ? experimentGroup === undefined
                    ? ""
                    : experimentGroup
                  : displayGroup
              }
            />
          );
        }
      })}
    </div>
  );
};
