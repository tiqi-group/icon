import { Box, Card, CardContent, Grid, Typography } from "@mui/material";
import { useParams } from "react-router";
import { useExperimentData } from "../hooks/useExperimentData";
import ResultChannelPlot from "../components/ResultChannelPlot";
import { useEffect, useState } from "react";
import { ExperimentMetadata } from "../types/ExperimentMetadata";
import { runMethod } from "../socket";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";
import { JobStatusIndicator } from "../components/JobStatusIndicator";
import { useJobInfo } from "../hooks/useJobInfo";
import { useJobRunInfo } from "../hooks/useJobRunInfo";

export function JobViewerPage() {
  const { jobId } = useParams();
  const [experimentMetadata, setExperimentMetadata] =
    useState<ExperimentMetadata | null>(null);

  const jobInfo = useJobInfo(jobId);
  const jobRunInfo = useJobRunInfo(jobId);
  const experimentData = useExperimentData(jobId);

  useEffect(() => {
    if (jobInfo?.experiment_source.experiment_id)
      runMethod("experiments.get_experiments", [], {}, (ack) => {
        setExperimentMetadata(
          deserialize(ack as SerializedObject)[
            jobInfo?.experiment_source.experiment_id
          ] as ExperimentMetadata,
        );
      });
  }, [jobInfo]);

  return (
    <Box p={2}>
      <Grid container spacing={2}>
        <Grid size={{ sm: 12, md: 4 }}>
          <Card>
            <CardContent>
              <div style={{ display: "flex", alignItems: "center" }}>
                <JobStatusIndicator status={jobRunInfo?.status} log={jobRunInfo?.log} />
                <Typography variant="h6">
                  {experimentMetadata?.constructor_kwargs.name} (
                  {experimentMetadata?.class_name}) - {jobId}
                </Typography>
              </div>
              <Typography variant="body2">
                {jobRunInfo?.scheduled_time ? (
                  <>Scheduled: {jobRunInfo.scheduled_time}</>
                ) : (
                  <>Created: {jobInfo?.created}</>
                )}
              </Typography>
              <Typography variant="body1">Scheduled: {jobInfo?.status}</Typography>
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
