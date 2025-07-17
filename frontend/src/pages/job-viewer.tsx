import { Box, Button, Card, CardContent, Grid, Typography } from "@mui/material";
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
import { cancelJob } from "../utils/cancelJob";
import { JobStatus } from "../types/enums";

export function JobViewerPage() {
  const { jobId } = useParams();
  const [experimentMetadata, setExperimentMetadata] =
    useState<ExperimentMetadata | null>(null);

  const jobInfo = useJobInfo(jobId);
  const jobRunInfo = useJobRunInfo(jobId);
  const { experimentData, experimentDataError } = useExperimentData(jobId);

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
        <Grid size={{ sm: 12, lg: 5 }}>
          <Card>
            <CardContent>
              <div style={{ display: "flex", alignItems: "center" }}>
                <JobStatusIndicator status={jobRunInfo?.status} log={jobRunInfo?.log} />
                <Typography variant="h6">
                  {jobId}
                  {experimentMetadata?.constructor_kwargs.name && (
                    <>
                      {" "}
                      - {experimentMetadata?.constructor_kwargs.name} (
                      {experimentMetadata?.class_name})
                    </>
                  )}
                </Typography>
                {jobInfo?.status !== JobStatus.PROCESSED && (
                  <>
                    <div style={{ flexGrow: 1 }} />
                    <Button
                      variant="contained"
                      color="error"
                      disabled={jobInfo === null}
                      size="small"
                      onClick={() => {
                        if (jobId) cancelJob(Number(jobId));
                      }}
                    >
                      Cancel
                    </Button>
                  </>
                )}
              </div>
              <Typography variant="body2">
                {jobRunInfo?.scheduled_time ? (
                  <>Scheduled: {jobRunInfo.scheduled_time}</>
                ) : (
                  <>Created: {jobInfo?.created}</>
                )}
              </Typography>
              <Typography variant="body1">{jobInfo?.status}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ sm: 12, lg: 7 }}>
          {experimentDataError ? (
            <Card>
              <CardContent>
                <Typography variant="h6" color="error">
                  Failed to load experiment data
                </Typography>
                <Typography variant="body2">{experimentDataError.message}</Typography>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent>
                <ResultChannelPlot experimentData={experimentData} />
              </CardContent>
            </Card>
          )}
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
