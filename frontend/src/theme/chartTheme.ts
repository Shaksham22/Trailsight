import { DATA_VISUALIZATION_COLORS } from "./palette.ts";
import type { ResolvedTheme } from "./theme.ts";

export const ACCOUNT_BANK_COUNTRY_SEMANTICS = {
  root: { seriesName: "Root Bank Country", legendLabel: "Root Bank Country", role: "ROOT" },
  connected: { seriesName: "Connected Bank Countries", legendLabel: "Connected Bank Country", role: "CONNECTED" },
  outgoing: { seriesName: "Outgoing", legendLabel: "Outgoing account activity", direction: "ROOT_TO_CONNECTED" },
  incoming: { seriesName: "Incoming", legendLabel: "Incoming account activity", direction: "CONNECTED_TO_ROOT" },
} as const;

export interface VisualizationTheme {
  chartCanvas: string;
  chartTooltipBackground: string;
  chartTooltipBorder: string;
  chartTooltipText: string;
  chartLabel: string;
  chartAxis: string;
  chartAxisLine: string;
  chartGrid: string;
  mapLand: string;
  mapBorder: string;
  mapHover: string;
  routeSending: string;
  routeReceiving: string;
  routeLine: string;
  mapRoot: string;
  mapRootBorder: string;
  mapRootHover: string;
  mapRootHoverBorder: string;
  mapRootMarker: string;
  mapRootMarkerBorder: string;
  mapRootLabel: string;
  mapRootLabelBackground: string;
  mapRootLabelBorder: string;
  mapConnected: string;
  mapConnectedBorder: string;
  mapConnectedHover: string;
  mapConnectedHoverBorder: string;
  mapConnectedMarker: string;
  mapConnectedMarkerBorder: string;
  mapConnectedLabel: string;
  mapConnectedLabelBackground: string;
  flowOutgoing: string;
  flowIncoming: string;
  networkRootFill: string;
  networkRootBorder: string;
  networkCounterpartyFill: string;
  networkCounterpartySelectedFill: string;
  networkCounterpartyBorder: string;
  networkCounterpartySelectedBorder: string;
  networkRootLabel: string;
  networkCounterpartyLabel: string;
  networkEdgeOutgoing: string;
  networkEdgeIncoming: string;
  networkEdgeSelected: string;
  seriesIncoming: string;
  seriesOutgoing: string;
  seriesCount: string;
  browserThemeColor: string;
}

const darkData = DATA_VISUALIZATION_COLORS.DARK;
const lightData = DATA_VISUALIZATION_COLORS.LIGHT;

export const VISUALIZATION_THEMES = {
  DARK: {
    chartCanvas: "#12171D",
    chartTooltipBackground: "#20262E", chartTooltipBorder: "#3B4552", chartTooltipText: "#F1F5F9",
    chartLabel: "#CBD5E1", chartAxis: "#7F8A98", chartAxisLine: "#536171", chartGrid: "#2C333D",
    mapLand: "#20262E", mapBorder: "#3A4655", mapHover: "#2A323C",
    routeSending: darkData.blue, routeReceiving: darkData.violet, routeLine: darkData.blue,
    mapRoot: "#D6A62E", mapRootBorder: "#F0C45A", mapRootHover: "#E0B441", mapRootHoverBorder: "#F7D67A",
    mapRootMarker: "#D6A62E", mapRootMarkerBorder: "#F0C45A", mapRootLabel: "#FDE9A8", mapRootLabelBackground: "rgba(15,18,22,.90)", mapRootLabelBorder: "#80661E",
    mapConnected: "#2A9DB8", mapConnectedBorder: "#67E8F9", mapConnectedHover: "#35AEC7", mapConnectedHoverBorder: "#A5F3FC",
    mapConnectedMarker: "#38BDF8", mapConnectedMarkerBorder: "#A5F3FC", mapConnectedLabel: "#BAE6FD", mapConnectedLabelBackground: "rgba(15,18,22,.88)",
    flowOutgoing: darkData.violet, flowIncoming: "#34D399",
    networkRootFill: "#3B82F6", networkRootBorder: darkData.blue, networkCounterpartyFill: "#303844", networkCounterpartySelectedFill: "#25384A",
    networkCounterpartyBorder: "#64748B", networkCounterpartySelectedBorder: darkData.blue, networkRootLabel: "#F8FAFC", networkCounterpartyLabel: "#CBD5E1",
    networkEdgeOutgoing: "#536171", networkEdgeIncoming: "#8B7FD1", networkEdgeSelected: darkData.blue,
    seriesIncoming: darkData.teal, seriesOutgoing: darkData.violet, seriesCount: "#64748B",
    browserThemeColor: "#0F1216",
  },
  LIGHT: {
    chartCanvas: "#FAFBFC",
    chartTooltipBackground: "#FFFFFF", chartTooltipBorder: "#CBD5E1", chartTooltipText: "#172033",
    chartLabel: "#334155", chartAxis: "#738091", chartAxisLine: "#94A3B8", chartGrid: "#E2E8F0",
    mapLand: "#EDF1F5", mapBorder: "#C6D0DC", mapHover: "#DEE5EC",
    routeSending: lightData.blue, routeReceiving: lightData.violet, routeLine: lightData.blue,
    mapRoot: "#C78B18", mapRootBorder: "#8A5B05", mapRootHover: "#D39A2C", mapRootHoverBorder: "#6B4704",
    mapRootMarker: "#C78B18", mapRootMarkerBorder: "#8A5B05", mapRootLabel: "#4B350B", mapRootLabelBackground: "rgba(255,255,255,.94)", mapRootLabelBorder: "#A06E0E",
    mapConnected: "#0E7490", mapConnectedBorder: "#155E75", mapConnectedHover: "#0F829F", mapConnectedHoverBorder: "#164E63",
    mapConnectedMarker: "#0891B2", mapConnectedMarkerBorder: "#155E75", mapConnectedLabel: "#164E63", mapConnectedLabelBackground: "rgba(255,255,255,.94)",
    flowOutgoing: lightData.violet, flowIncoming: "#087F5B",
    networkRootFill: lightData.blue, networkRootBorder: "#1D4ED8", networkCounterpartyFill: "#DCE3EA", networkCounterpartySelectedFill: "#D7E9F8",
    networkCounterpartyBorder: "#7C8A9A", networkCounterpartySelectedBorder: "#1677C8", networkRootLabel: "#FFFFFF", networkCounterpartyLabel: "#334155",
    networkEdgeOutgoing: "#94A3B8", networkEdgeIncoming: lightData.violet, networkEdgeSelected: lightData.blue,
    seriesIncoming: lightData.teal, seriesOutgoing: lightData.violet, seriesCount: "#94A3B8",
    browserThemeColor: "#F4F6F8",
  },
} as const satisfies Record<ResolvedTheme, VisualizationTheme>;
