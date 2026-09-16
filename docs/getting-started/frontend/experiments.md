The experiments page shows a list of experiments on the left. This list is parsed from the experiment library ICON connects to.
When you click on an experiment, you will be greeted with the scan interface on the top. This allows you to define parameters you want to scan, the priority of the scan (number between 1 and 20), the number of shots for each data point, and the number of scan repetitions.

When you scan more than one parameter, the scan mode determines how their values are combined:

- **Mesh Scan** (default) scans the mesh of all possible combinations. Scanning parameters with `n` and `m` points yields `n * m` data points.
- **Correlated Scan** steps through all scan parameters at the same time and yields a one-dimensional list of `n` data points: the i-th data point sets every parameter to its i-th value. This requires every scan parameter to have the same number of points, and the result is plotted as a line against the first scan parameter.

A "Real Time" parameter is scanned as an outer loop and is not correlated with the other parameters.

On the bottom, you will get the display groups defined for the experiment (instance). These are either local parameters (i.e. parameters scoped to the experiment instance), global parmaeters (i.e. parameters that) or device parameters
