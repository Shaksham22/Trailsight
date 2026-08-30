/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_TRAILSIGHT_API_BASE_URL?: string;
  readonly VITE_TRAILSIGHT_DATA_MODE?: "real" | "fixture";
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
