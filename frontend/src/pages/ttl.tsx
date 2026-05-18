import { TTLControlPanel } from "../components/ttl/TTLControlPanel";
import { useTTLState } from "../hooks/useTTLState";

export default function TTLPage() {
  const ttl = useTTLState();
  return <TTLControlPanel ttl={ttl} />;
}
