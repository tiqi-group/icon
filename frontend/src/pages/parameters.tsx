import Typography from "@mui/material/Typography";
import { useContext } from "react";
import { Divider } from "@mui/material";
import { ParameterGroupDisplay } from "../components/ParameterGroupDisplay";
import { Accordion, AccordionSummary, AccordionDetails } from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import { ParameterDisplayGroupsContext } from "../contexts/ParameterDisplayGroupsContext";

const ParameterPage = () => {
  const [, namespaceGroups] = useContext(ParameterDisplayGroupsContext);

  return (
    <>
      {Object.entries(namespaceGroups).map(([namespace, displayGroupList]) => (
        <Accordion
          key={namespace}
          disableGutters // Removes extra padding/margin from Accordion
          square
          sx={{ "&:before": { display: "none" } }}
        >
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="h5">{namespace}</Typography>
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
      ))}
    </>
  );
};

export default ParameterPage;
