import { useEffect } from "react";
import { socket } from "../socket";
import { VirtualizedJobList } from "../components/VirtualisedJobList";

export function DataPage() {
  return <VirtualizedJobList />;
}
