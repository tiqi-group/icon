import * as React from "react";
import Box from "@mui/material/Box";
import ListItem from "@mui/material/ListItem";
import ListItemText from "@mui/material/ListItemText";
import { FixedSizeList, ListChildComponentProps } from "react-window";
import PlotInterface from "../components/PlotInterfaceComponent";
import { compareJobs } from "../utils/compareJobs";
import { JobsContext } from "../contexts/JobsContext";

export function VirtualizedJobList() {
  const jobs = React.useContext(JobsContext);

  const sortedJobs = React.useMemo(() => {
    return Object.values(jobs).sort(compareJobs);
  }, [jobs]);

  const ITEM_HEIGHT = 400; // adjust depending on plot height

  const renderRow = ({ index, style }: ListChildComponentProps) => {
    const job = sortedJobs[index];

    return (
      <ListItem style={style} key={job.id} component="div" disablePadding>
        <Box
          display="flex"
          sx={{ flexDirection: "column", width: "100%", height: "100%" }}
        >
          <ListItemText
            primary={`Job ${job.id}: ${job.status}, priority ${job.priority}`}
            secondary={`Experiment ID: ${job.experiment_source.experiment_id}`}
          />
          <PlotInterface jobId={job.id} />
        </Box>
      </ListItem>
    );
  };

  return (
    <Box
      sx={{
        width: "100%",
        height: "100%", // or fixed height
        // maxWidth: 1000,
        bgcolor: "background.paper",
      }}
    >
      <FixedSizeList
        height={window.innerHeight}
        width="100%"
        itemSize={ITEM_HEIGHT}
        itemCount={sortedJobs.length}
        overscanCount={2}
      >
        {renderRow}
      </FixedSizeList>
    </Box>
  );
}
