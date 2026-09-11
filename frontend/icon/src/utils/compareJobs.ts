import { JobStatus } from "../types/enums";
import { Job } from "../types/Job";

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
export function compareJobs(a: Job, b: Job): number {
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
