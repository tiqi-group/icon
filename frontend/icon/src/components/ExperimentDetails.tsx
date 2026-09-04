import { useContext } from "react";
import {
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { ExperimentsContext } from "../contexts/ExperimentsContext";
import { ParameterGroupDisplay } from "./ParameterGroupDisplay";
import ScanInterface from "./scanInterface/ScanInterfaceComponent";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";
import { ScannableParameterInterface } from "./devices/ScannableParameterInterface";

const ExperimentDetails = ({ experimentKey }: { experimentKey: string }) => {
  const experiments = useContext(ExperimentsContext);
  const experiment = experiments[experimentKey];
  const reachableDevices = Object.entries(useContext(DeviceInfoContext))
    .filter(([, d]) => d.reachable)
    .map(([name]) => name);

  if (!experiment) {
    return (
      <Typography>Select an experiment from the left to view details here.</Typography>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <ScanInterface experimentId={experimentKey} />
      {Object.keys(experiment.parameters).map((group) => (
        <Accordion
          key={experimentKey + group}
          defaultExpanded
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
        </Accordion>
      ))}

      {experiment.device_parameter_groups?.map((deviceName) => {
        const isReachable = reachableDevices.includes(deviceName);

        return (
          <Accordion key={`Device ${deviceName}`} defaultExpanded disableGutters square>
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
          </Accordion>
        );
      })}
    </div>
  );
};

export default ExperimentDetails;
