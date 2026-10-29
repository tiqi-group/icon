{%
    include-markdown "../../README.md"
    start="<!--configuration-start-->"
    end="<!--configuration-end-->"
    heading-offset=-2
%}

## Databases

* **HDF** - file format of the experiment results. Each experiment job gets its own HDF file. The result directory defaults to `"$(pwd)/output"` and can be configured in the configuration file:
  ```yaml
  data:
    results_dir: /my/results/output/dir/
  ```

    ICON creates the result directory at startup if it does not exist, but not
    its parent directories. If it cannot be created or accessed, ICON logs a
    warning, and scans fail with an error naming the directory until this is
    fixed. Within it, result files are grouped into one folder per day
    (`yyyy-mm-dd`), which ICON creates as needed. Each file is named after the
    run's scheduled time in ISO 8601 basic format and the experiment name,
    reduced to characters that are safe on every platform:

    ```
    2026-10-29/20261029T125148.123456_Ramsey_fine.h5
    ```

    Earlier versions stored result files directly in the result directory,
    named like `2026-10-29 12:51:48.123456.h5`. ICON no longer reads them there
    and refuses to start while any remain. With ICON stopped, move and rename
    them with:

    ```bash
    icon-migrate-results-dir --config /path/to/config.yaml --dry-run  # preview
    icon-migrate-results-dir --config /path/to/config.yaml
    ```

    A result file may be locked by another process (for instance an analysis
    script opening the same file). ICON waits for such a lock to be released
    and gives up after `h5_open_timeout_seconds`, which defaults to `30.0`:

    ```yaml
    data:
      h5_open_timeout_seconds: 60.0
    ```

* **SQLite** - stores metadata about jobs and devices. By default, ICON will create `icon.db` in the current working directory. You can override this path in the config file:

    ```yaml
    databases:
      sqlite:
        file: /my/custom/sqlite/path/icon.db
    ```

* **InfluxDB** - stores parameter time series. Both InfluxDB v1 and v2 are supported (v3 may work but is untested).

    === "InfluxDB v1"

        ```yaml
        databases:
          influxdbv1:
            database: testing
            host: localhost
            measurement: Experiment Parameters
            password: passw0rd
            port: 8086
            username: tester
            ...
        ```

    === "InfluxDB v2"

        ```yaml
        databases:
          influxdbv1:
            database: testing
            host: localhost
            measurement: Experiment Parameters
            password: <influxdb v2 token>
            port: 8086
            ...
        ```
