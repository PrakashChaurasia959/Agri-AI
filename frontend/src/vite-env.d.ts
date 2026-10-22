/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL of the API, relative to the origin by default. */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
