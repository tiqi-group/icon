import { useMemo } from "react";
import { ButtonComponent } from "./parameterComponents/Button";
import { Output } from "./parameterComponents/Output";
import { ParameterNumberComponent } from "./parameterComponents/ParameterNumberComponent";
import { Combobox } from "./parameterComponents/Combobox";
import { useScanContext } from "../hooks/useScanContext";
import { getScanIndex } from "../utils/scanUtils";
import { useResponsiveGridColumns } from "../hooks/useResponsiveGridColumns";
import { ParameterMetadata } from "../types/ExperimentMetadata";
import { ParameterValue } from "../types/ExperimentData";

interface ParameterGroupDisplayProps {
  parameters: Record<string, ParameterMetadata>;
  values?: Record<string, ParameterValue>;
  experimentKey?: string;
  experimentGroup?: string;
  namespace?: string;
  displayGroup?: string;
  readOnly?: boolean;
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
  parameters,
  values,
  readOnly = false,
}: ParameterGroupDisplayProps) => {
  const { scannedParamKeys, handleRightClick } = useScanContext();
  const gridTemplateColumns = useResponsiveGridColumns();

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
        const value = values?.[paramId]?.value;

        if (readOnly) {
          return (
            <Output
              id={paramId}
              label={paramMetadata.display_name}
              value={value}
              defaultValue={paramMetadata.default_value}
              scanIndex={scanIndex}
              description={paramId}
            />
          );
        }

        if (paramId.includes("param_type='ParameterTypes.BOOLEAN'")) {
          return (
            <ButtonComponent
              onContextMenu={handleRightClick}
              scanIndex={scanIndex}
              key={paramId}
              id={paramId}
              displayName={paramMetadata.display_name}
              defaultValue={Boolean(paramMetadata.default_value)}
              value={value != null ? Boolean(value) : undefined}
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
              value={value?.toString()}
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
              value={value?.toString()}
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
