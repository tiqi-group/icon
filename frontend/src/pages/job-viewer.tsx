import { Box, Card, CardContent, Grid, Typography } from "@mui/material";
import { useParams } from "react-router";
import { useExperimentData } from "../hooks/useExperimentData";
import ResultChannelPlot from "../components/ResultChannelPlot";

export function JobViewerPage() {
  const { jobId } = useParams();
  const experimentData = useExperimentData(jobId);

  return (
    <Box p={2}>
      <Grid container spacing={2}>
        <Grid size={{ sm: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6">Experiment Info</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ sm: 12, md: 8 }}>
          <Card>
            <CardContent>
              <ResultChannelPlot experimentData={experimentData} />
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <Card>
            <CardContent>
              <Typography variant="h6">Parameter Values</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
