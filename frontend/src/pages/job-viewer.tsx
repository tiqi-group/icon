import { useParams } from "react-router";
import { JobView } from "../components/JobView";

export function JobViewerPage() {
  const { jobId } = useParams();

  return <JobView jobId={jobId} />;
}
