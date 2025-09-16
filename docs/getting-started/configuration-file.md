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
