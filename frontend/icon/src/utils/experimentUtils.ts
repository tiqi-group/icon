export function getExperimentNameFromExperimentId(experimentId: string): string {
  const match = experimentId.match(/\((.*?)\)/);
  return match ? match[1] : experimentId;
}

export function experimentIdToNamespace(experimentId: string): string {
  // Convert "path.ClassName (InstanceName)" to "path.ClassName.InstanceName"
  const match = experimentId.match(/^(.+)\s+\((.+)\)$/);
  if (match) {
    const [, classPath, instanceName] = match;
    return `${classPath.trim()}.${instanceName.trim()}`;
  }
  return experimentId;
}
