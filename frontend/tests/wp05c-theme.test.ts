import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  APPEARANCE_MODES,
  THEME_STORAGE_KEY,
  persistAppearancePreference,
  readAppearancePreference,
  resolveTheme,
  type ThemeStorage,
} from "../src/theme/theme.ts";
import { ACCOUNT_BANK_COUNTRY_SEMANTICS, VISUALIZATION_THEMES } from "../src/theme/chartTheme.ts";
import { DATA_VISUALIZATION_COLORS, STATUS_THEME_COLORS } from "../src/theme/palette.ts";

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, "..");
const source = async (path: string) => readFile(resolve(root, path), "utf8");

function cssToken(block: string, name: string) {
  return block.match(new RegExp(`--${name}:([^;]+)`))?.[1]?.trim() ?? "";
}

function themeBlocks(styles: string) {
  return {
    DARK: styles.match(/^:root\s*\{([\s\S]*?)\}/)?.[1] ?? "",
    LIGHT: styles.match(/\[data-theme="light"\]\s*\{([\s\S]*?)\}/)?.[1] ?? "",
  };
}

function hexChroma(value: string) {
  const match = value.match(/^#([0-9a-f]{6})$/i);
  assert.ok(match, `${value} must be a six-digit hex color`);
  const channels = [0, 2, 4].map((offset) => Number.parseInt(match[1].slice(offset, offset + 2), 16));
  return Math.max(...channels) - Math.min(...channels);
}

function assertGreenSemanticRole(
  color: { readonly text: string; readonly border: string; readonly background: string },
  label: string,
) {
  for (const [role, value] of Object.entries(color)) {
    const match = value.match(/^#([0-9a-f]{6})$/i);
    assert.ok(match, `${label} ${role} must be a six-digit hex color`);
    const [red, green, blue] = [0, 2, 4].map((offset) => Number.parseInt(match[1].slice(offset, offset + 2), 16));
    assert.ok(green > red && green > blue, `${label} ${role} must use the green semantic role`);
  }
}

function memoryStorage(initial: Record<string, string> = {}) {
  const values = new Map(Object.entries(initial));
  const calls: string[] = [];
  const storage: ThemeStorage = {
    getItem(key) { calls.push(`get:${key}`); return values.get(key) ?? null; },
    setItem(key, value) { calls.push(`set:${key}:${value}`); values.set(key, value); },
    removeItem(key) { calls.push(`remove:${key}`); values.delete(key); },
  };
  return { calls, storage, values };
}

test("appearance supports exactly SYSTEM, LIGHT, and DARK", () => {
  assert.deepEqual([...APPEARANCE_MODES], ["SYSTEM", "LIGHT", "DARK"]);
  assert.equal(readAppearancePreference(memoryStorage().storage), "SYSTEM");
  assert.equal(readAppearancePreference(memoryStorage({ [THEME_STORAGE_KEY]: "SEPIA" }).storage), "SYSTEM");
});

test("SYSTEM resolves from the OS preference", () => {
  assert.equal(resolveTheme("SYSTEM", false), "LIGHT");
  assert.equal(resolveTheme("SYSTEM", true), "DARK");
});

test("explicit LIGHT and DARK override the OS preference", () => {
  assert.equal(resolveTheme("LIGHT", true), "LIGHT");
  assert.equal(resolveTheme("DARK", false), "DARK");
});

test("explicit preference is persisted and SYSTEM clears the explicit override", () => {
  const { storage, values, calls } = memoryStorage();
  persistAppearancePreference(storage, "DARK");
  assert.equal(values.get(THEME_STORAGE_KEY), "DARK");
  assert.equal(readAppearancePreference(storage), "DARK");
  persistAppearancePreference(storage, "LIGHT");
  assert.equal(values.get(THEME_STORAGE_KEY), "LIGHT");
  persistAppearancePreference(storage, "SYSTEM");
  assert.equal(values.has(THEME_STORAGE_KEY), false);
  assert.ok(calls.every((call) => call.includes(THEME_STORAGE_KEY)));
});

test("unavailable browser storage degrades safely to SYSTEM", () => {
  const unavailable: ThemeStorage = {
    getItem() { throw new Error("blocked"); },
    setItem() { throw new Error("blocked"); },
    removeItem() { throw new Error("blocked"); },
  };
  assert.equal(readAppearancePreference(unavailable), "SYSTEM");
  assert.doesNotThrow(() => persistAppearancePreference(unavailable, "DARK"));
  assert.equal(readAppearancePreference(null), "SYSTEM");
});

test("semantic AML roles remain fixed and visually distinct in both themes", async () => {
  for (const theme of ["LIGHT", "DARK"] as const) {
    assert.deepEqual(Object.keys(STATUS_THEME_COLORS[theme]), ["HIGH", "MEDIUM", "LOW", "UNSCORED"]);
    const colors = Object.values(STATUS_THEME_COLORS[theme]);
    assert.equal(new Set(colors.map((color) => color.text)).size, 4, `${theme} AML text colors must be distinct`);
    assert.notDeepEqual(STATUS_THEME_COLORS[theme].LOW, STATUS_THEME_COLORS[theme].UNSCORED, `${theme} LOW must remain visually distinct from UNSCORED`);
    assertGreenSemanticRole(STATUS_THEME_COLORS[theme].LOW, `${theme} LOW`);
  }
  const styles = await source("src/styles.css");
  const blocks = themeBlocks(styles);
  for (const theme of ["LIGHT", "DARK"] as const) {
    const low = {
      text: cssToken(blocks[theme], "status-low-text"),
      border: cssToken(blocks[theme], "status-low-border"),
      background: cssToken(blocks[theme], "status-low-bg"),
    };
    const unscored = {
      text: cssToken(blocks[theme], "status-unscored-text"),
      border: cssToken(blocks[theme], "status-unscored-border"),
      background: cssToken(blocks[theme], "status-unscored-bg"),
    };
    assert.deepEqual(low, STATUS_THEME_COLORS[theme].LOW, `${theme} LOW CSS variables must match the palette`);
    assert.notDeepEqual(low, unscored, `${theme} LOW CSS variables must remain visually distinct from UNSCORED`);
    assertGreenSemanticRole(low, `${theme} LOW CSS`);
  }
  for (const status of ["high", "medium", "low", "unscored"]) {
    for (const role of ["text", "border", "bg"]) assert.match(styles, new RegExp(`--status-${status}-${role}:`));
    assert.match(styles, new RegExp(`\\.pill--${status}\\{[^}]+var\\(--status-${status}-text\\)[^}]+var\\(--status-${status}-border\\)[^}]+var\\(--status-${status}-bg\\)`));
  }
  assert.doesNotMatch(styles, /SAFE|NORMAL|CLEARED|NO RISK/i);
});

test("semantic surface architecture separates hierarchy and dark chrome is neutral graphite", async () => {
  const styles = await source("src/styles.css");
  const blocks = themeBlocks(styles);
  for (const block of Object.values(blocks)) {
    for (const token of ["bg-app", "bg-surface", "bg-surface-subtle", "bg-elevated", "bg-hover", "bg-selected", "border-subtle", "border-strong", "text-primary", "text-secondary", "text-muted", "accent", "accent-hover", "accent-soft", "focus-ring"]) {
      assert.ok(cssToken(block, token), `${token} must exist in both themes`);
    }
  }
  assert.notEqual(cssToken(blocks.LIGHT, "bg-app"), cssToken(blocks.LIGHT, "bg-surface"));
  assert.notEqual(cssToken(blocks.DARK, "bg-app"), cssToken(blocks.DARK, "bg-surface"));
  assert.notEqual(cssToken(blocks.DARK, "bg-surface"), cssToken(blocks.DARK, "bg-surface-subtle"));
  assert.ok(hexChroma(cssToken(blocks.DARK, "bg-app")) <= 12, "dark app background must be neutral, not navy");
  assert.doesNotMatch(blocks.DARK, /#07111D|#0A1624|#0D1B2A/i);
});

test("visualization palette and semantic chart configuration have light and dark variants", () => {
  assert.deepEqual(Object.keys(DATA_VISUALIZATION_COLORS).sort(), ["DARK", "LIGHT"]);
  assert.deepEqual(Object.keys(VISUALIZATION_THEMES).sort(), ["DARK", "LIGHT"]);
  for (const series of ["blue", "teal", "violet", "orange", "rose", "green"] as const) {
    assert.notEqual(DATA_VISUALIZATION_COLORS.LIGHT[series], DATA_VISUALIZATION_COLORS.DARK[series]);
  }
  assert.notEqual(VISUALIZATION_THEMES.LIGHT.chartCanvas, VISUALIZATION_THEMES.DARK.chartCanvas);
  assert.notEqual(VISUALIZATION_THEMES.LIGHT.mapLand, VISUALIZATION_THEMES.DARK.mapLand);
  assert.notEqual(VISUALIZATION_THEMES.LIGHT.chartTooltipBackground, VISUALIZATION_THEMES.DARK.chartTooltipBackground);
  assert.notEqual(VISUALIZATION_THEMES.LIGHT.networkCounterpartyLabel, VISUALIZATION_THEMES.DARK.networkCounterpartyLabel);
  for (const theme of ["LIGHT", "DARK"] as const) {
    assert.notEqual(VISUALIZATION_THEMES[theme].flowOutgoing, VISUALIZATION_THEMES[theme].flowIncoming);
    assert.notEqual(VISUALIZATION_THEMES[theme].mapRoot, VISUALIZATION_THEMES[theme].mapConnected);
    assert.notEqual(VISUALIZATION_THEMES[theme].networkRootFill, VISUALIZATION_THEMES[theme].networkCounterpartyFill);
  }
});

test("map direction and root/connected meanings do not change by theme", () => {
  assert.deepEqual(ACCOUNT_BANK_COUNTRY_SEMANTICS, {
    root: { seriesName: "Root Bank Country", legendLabel: "Root Bank Country", role: "ROOT" },
    connected: { seriesName: "Connected Bank Countries", legendLabel: "Connected Bank Country", role: "CONNECTED" },
    outgoing: { seriesName: "Outgoing", legendLabel: "Outgoing account activity", direction: "ROOT_TO_CONNECTED" },
    incoming: { seriesName: "Incoming", legendLabel: "Incoming account activity", direction: "CONNECTED_TO_ROOT" },
  });
  for (const theme of ["LIGHT", "DARK"] as const) {
    assert.equal(VISUALIZATION_THEMES[theme].flowOutgoing, DATA_VISUALIZATION_COLORS[theme].violet);
    assert.notEqual(VISUALIZATION_THEMES[theme].flowIncoming, VISUALIZATION_THEMES[theme].flowOutgoing);
    assert.notEqual(VISUALIZATION_THEMES[theme].mapRoot, VISUALIZATION_THEMES[theme].mapConnected);
  }
});

test("theme persistence has no backend request path", async () => {
  const themeSource = await source("src/theme/theme.ts");
  const providerSource = await source("src/theme/ThemeProvider.tsx");
  assert.doesNotMatch(`${themeSource}\n${providerSource}`, /fetch\s*\(|\/api\//);
  const { storage, calls } = memoryStorage();
  persistAppearancePreference(storage, "DARK");
  assert.deepEqual(calls, [`set:${THEME_STORAGE_KEY}:DARK`]);
});

test("startup resolves appearance before the application module and the header control is accessible", async () => {
  const html = await source("index.html");
  assert.ok(html.indexOf("trailsight.appearance") < html.indexOf('src="/src/main.tsx"'));
  assert.match(html, /prefers-color-scheme: dark/);
  const ui = await source("src/components/ui.tsx");
  assert.match(ui, /role="group" aria-label="Appearance mode"/);
  assert.match(ui, /aria-pressed=/);
});
