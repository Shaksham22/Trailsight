import * as implementation from "./fixtures.ts";

/** Explicit Vite fixture-mode provider selected at build time by vite.config.ts. */
export const fixtureApi: typeof import("./fixtures.ts") | null = implementation;
