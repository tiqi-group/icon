export interface Configuration {
  version: number;
  date: {
    timezone: string;
  };
  databases: {
    influxdbv1: {
      database: string;
      headers: Record<string, string>;
      host: string;
      password: string;
      port: number;
      ssl: boolean;
      username: string;
      verify_ssl: boolean;
    };
  };
  experiment_library: {
    dir: string;
    git_repository: string;
    update_interval: number;
  };
  hardware: {
    host: string;
    port: number;
  };
  health_check: {
    interval_seconds: number;
  };
  server: {
    host: string;
    port: number;
    pre_processing: {
      workers: number;
    };
  };
  data: {
    results_dir: string;
  };
}
