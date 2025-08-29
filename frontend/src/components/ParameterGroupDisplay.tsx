import { useContext, useMemo } from "react";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import { ParameterDisplayGroupsContext } from "../contexts/ParameterDisplayGroupsContext";
import { ButtonComponent } from "./parameterComponents/Button";
import { ParameterNumberComponent } from "./parameterComponents/ParameterNumberComponent";
import { Combobox } from "./parameterComponents/Combobox";
import { useScanContext } from "../hooks/useScanContext";
import { getScanIndex } from "../utils/getScanIndex";
import { useResponsiveGridColumns } from "../hooks/useResponsiveGridColumns";

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
  const { scannedParamKeys, handleRightClick } = useScanContext();
  const gridTemplateColumns = useResponsiveGridColumns();

  const experiments = useContext(ExperimentsContext);
  const { parameterDisplayGroups } = useContext(ParameterDisplayGroupsContext);

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
        columnGap: 24,
        gridTemplateColumns,
      }}
    >
      {sortedParameters.map(([paramId, paramMetadata]) => {
        const scanIndex = getScanIndex(paramId, scannedParamKeys);

        if (paramId.includes("param_type='ParameterTypes.BOOLEAN'")) {
          return (
            <ButtonComponent
              onContextMenu={handleRightClick}
              scanIndex={scanIndex}
              key={paramId}
              id={paramId}
              displayName={paramMetadata.display_name}
              defaultValue={Boolean(paramMetadata.default_value)}
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
          return (
            <Combobox
              key={paramId}
              id={paramId}
              defaultValue={String(paramMetadata.default_value)}
              displayName={paramMetadata.display_name}
              allowedValues={paramMetadata.allowed_values!}
            />
          );
        } else {
          return (
            <ParameterNumberComponent
              onContextMenu={handleRightClick}
              scanIndex={scanIndex}
              key={paramId}
              id={paramId}
              displayName={paramMetadata.display_name}
              defaultValue={String(paramMetadata.default_value)}
              min={paramMetadata?.min_value}
              max={paramMetadata?.max_value}
              unit={paramMetadata?.unit}
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
