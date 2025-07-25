export function getExperimentNameFromExperimentId(experimentId: string): string {
  const match = experimentId.match(/\((.*?)\)/);
  return match ? match[1] : experimentId;
}
