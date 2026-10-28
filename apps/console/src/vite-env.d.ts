/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the HIVE core service. Defaults to the local service. */
  readonly VITE_HIVE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
