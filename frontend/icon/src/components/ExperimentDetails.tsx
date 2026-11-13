import { useContext } from "react";
import { Typography, AccordionSummary, AccordionDetails } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import { ScanProvider } from "../contexts/ScanProvider";
import { ParameterGroupDisplay } from "./ParameterGroupDisplay";
import ScanInterface from "./scanInterface/ScanInterfaceComponent";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";
import { ScannableParameterInterface } from "./devices/ScannableParameterInterface";
import { RememberedAccordion } from "./RememberedAccordion";
import { useRememberedGroupOrder } from "../hooks/useRememberedGroupOrder";

const ExperimentDetails = ({ experimentKey }: { experimentKey: string }) => {
  const experiments = useContext(ExperimentsContext);
  const experiment = experiments[experimentKey];
  const reachableDevices = Object.entries(useContext(DeviceInfoContext))
    .filter(([, d]) => d.reachable)
    .map(([name]) => name);
  const groups = useRememberedGroupOrder(
    `parameterGroupOrder_${experimentKey}`,
    Object.keys(experiment?.parameters ?? {}),
  );
  const deviceGroups = useRememberedGroupOrder(
    `deviceGroupOrder_${experimentKey}`,
    experiment?.device_parameter_groups ?? [],
  );

  if (!experiment) {
    return (
      <Typography>Select an experiment from the left to view details here.</Typography>
    );
  }

  return (
    // Keyed so each experiment mounts with its own scan state.
    <ScanProvider key={experimentKey} experimentId={experimentKey}>
      <div style={{ display: "flex", flexDirection: "column" }}>
        <ScanInterface experimentId={experimentKey} />
        {groups.map((group) => (
          <RememberedAccordion
            key={experimentKey + group}
            storageKey={`expandedParameterGroups_${experimentKey}`}
            name={group}
            disableGutters // Removes extra padding/margin from Accordion
            square
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ m: 0 }}>
              <Typography variant="h6">{group}</Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ m: 0 }}>
              <ParameterGroupDisplay
                experimentKey={experimentKey}
                experimentGroup={group}
                parameters={experiments[experimentKey]?.parameters?.[group] || {}}
              />
            </AccordionDetails>
          </RememberedAccordion>
        ))}

        {deviceGroups.map((deviceName) => {
          const isReachable = reachableDevices.includes(deviceName);
          const section = `Device ${deviceName}`;

          return (
            <RememberedAccordion
              key={section}
              storageKey="expandedParameterGroups"
              name={section}
              disableGutters
              square
            >
              <AccordionSummary expandIcon={<ExpandMoreIcon />} sx={{ m: 0 }}>
                <Typography variant="h6">Device: {deviceName}</Typography>
              </AccordionSummary>
              <AccordionDetails sx={{ m: 0 }}>
                {isReachable ? (
                  <ScannableParameterInterface name={deviceName} />
                ) : (
                  <>Device not reachable</>
                )}
              </AccordionDetails>
            </RememberedAccordion>
          );
        })}
      </div>
    </ScanProvider>
  );
};

export default ExperimentDetails;
