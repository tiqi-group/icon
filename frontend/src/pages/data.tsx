import { useEffect, useState } from "react";
import { deserialize } from "../utils/deserializer";
import PlotInterface from "../components/PlotInterfaceComponent";
import { runMethod, socket } from "../socket";
import { SerializedObject } from "../types/SerializedObject";
import { Job } from "../types/Job";
import { JobStatus } from "../types/enums";

interface NewDataEvent {
  job: Job;
  scheduled_time: string;
}
interface JobUpdate {
  job_id: string;
  updated_properties: Record<string, string>;
}

/**
 * Comparator function to sort jobs by status, priority, and creation time.
 *
 * Sort order:
 *  1. Status:
 *     - 'processing' jobs come first
 *     - followed by 'submitted'
 *     - then 'processed'
 *  2. For 'processing' and 'submitted' jobs:
 *     - Sort by ascending priority (lower number = higher priority)
 *     - If priority is equal, sort by descending creation time (newest first)
 *  3. For 'processed' jobs:
 *     - Ignore priority, sort only by descending creation time
 *
 * @param a - First job to compare
 * @param b - Second job to compare
 * @returns - Negative if a < b, positive if a > b, 0 if equal (for use in Array.prototype.sort)
 */
function compareJobs(a: Job, b: Job): number {
  const statusOrder: Record<JobStatus, number> = {
    [JobStatus.PROCESSING]: 0,
    [JobStatus.SUBMITTED]: 1,
    [JobStatus.PROCESSED]: 2,
  };

  const statusDiff = statusOrder[a.status] - statusOrder[b.status];
  if (statusDiff !== 0) return statusDiff;

  if (a.status === JobStatus.PROCESSED && b.status === JobStatus.PROCESSED) {
    return new Date(b.created).getTime() - new Date(a.created).getTime(); // recent first
  }

  const priorityDiff = a.priority - b.priority;
  if (priorityDiff !== 0) return priorityDiff;

  return new Date(b.created).getTime() - new Date(a.created).getTime(); // recent first
}

export function DataPage() {
  const [scheduledJobs, setScheduledJobs] = useState<Record<string, Job>>({});

  // Subscribe to all experiment updates
  useEffect(() => {
    runMethod("scheduler.get_scheduled_jobs", [], {}, (result) => {
      setScheduledJobs(
        () => deserialize(result as SerializedObject) as Record<string, Job>,
      );
    });

    socket.on("new_experiment", (data: NewDataEvent) => {
      // Update scheduledJobs with the new experiment
      setScheduledJobs((scheduledJobs) => {
        return { ...scheduledJobs, [data.job.id]: data.job };
      });

      socket.emit("get_experiment_data", data.job.id);
    });
    socket.on("update_job", (data: JobUpdate) => {
      console.log("Received job update");
      console.log(data);
      setScheduledJobs((scheduledJobs) => {
        const job = scheduledJobs[data.job_id];
        // job not found, no update
        if (!job) return scheduledJobs;

        return {
          ...scheduledJobs,
          [data.job_id]: {
            ...job,
            status: data.updated_properties.status as JobStatus,
          },
        };
      });
    });
    socket.on("experiment_data", (data) => {
      console.log(data);
    });
    socket.on("experiment_data_point", (data) => {
      console.log(data);
    });
    return () => {
      socket.off("new_experiment");
      socket.off("experiment_data");
      socket.off("experiment_data_point");
      socket.off("update_job");
    };
  }, []);

  useEffect(() => {
    console.log("Scheduled jobs:");
    console.log(scheduledJobs);
  }, [scheduledJobs]);

  const sortedJobs = Object.values(scheduledJobs).sort(compareJobs);

  return (
    <ul>
      {sortedJobs.map((job) => (
        <li key={job.id}>
          Job ID: {job.id}, Name: {job.experiment_source.experiment_id}, Scheduled:{" "}
          {job.created}, Priority: {job.priority}, Status: {job.status}
        </li>
      ))}
    </ul>
  );
}
