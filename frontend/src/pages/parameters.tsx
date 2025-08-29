import Typography from "@mui/material/Typography";
import { useContext } from "react";
import { Divider } from "@mui/material";
import { ParameterGroupDisplay } from "../components/ParameterGroupDisplay";
import { Accordion, AccordionSummary, AccordionDetails } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { ParameterDisplayGroupsContext } from "../contexts/ParameterDisplayGroupsContext";

const getDisplayNameFromNamespace = (namespace: string): string => {
  if (namespace.endsWith(".globals.global_parameters")) return "Global Parameters";
  else {
    const namespaceParts = namespace.split(".");
    const experimentName = namespaceParts.at(-1);
    if (experimentName) return experimentName;
  }
  return namespace;
};

const ParameterPage = () => {
  const { parameterNamespaceToDisplayGroups: parameterNamespaceToDisplayGroups } =
    useContext(ParameterDisplayGroupsContext);

  return (
    <>
      {Object.entries(parameterNamespaceToDisplayGroups).map(
        ([namespace, displayGroupList]) => (
          <Accordion
            key={namespace}
            disableGutters
            sx={{ "&:before": { display: "none" } }}
          >
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <div>
                <Typography variant="h5">
                  {getDisplayNameFromNamespace(namespace)}
                </Typography>
                <Typography variant="body2">{namespace}</Typography>
              </div>
            </AccordionSummary>
            <AccordionDetails>
              {displayGroupList.map((displayGroup, index) => (
                <div key={namespace + " (" + displayGroup + ")"}>
                  <Typography variant="h6">{displayGroup}</Typography>
                  <ParameterGroupDisplay
                    namespace={namespace}
                    displayGroup={displayGroup}
                  />
                  {index < displayGroupList.length - 1 && <Divider sx={{ pt: 2 }} />}
                </div>
              ))}
            </AccordionDetails>
          </Accordion>
        ),
      )}
    </>
  );
};

export default ParameterPage;
