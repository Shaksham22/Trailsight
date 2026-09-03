import { useEffect, useMemo, useRef, useState } from "react";
import { BarChart, EffectScatterChart, GraphChart, LineChart, LinesChart, ScatterChart } from "echarts/charts";
import { GeoComponent, GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import type { ECElementEvent, EChartsCoreOption } from "echarts/core";
import worldGeo from "../assets/world.geo.json";
import type { AccountNetwork, ActivityContext, BankCountryFlowRow, BankCountryRoute } from "../api/types";
import { getBankCountryMapGeometryName } from "../lib/bankCountries";
import { accountBankCountryTooltip, activityBucketsForCurrency, activityCurrencies, buildAccountBankCountryVisualModel, buildRouteVisualModel, graphTruncationText } from "../lib/visualization";
import { useTheme } from "../theme/ThemeProvider";
import { ACCOUNT_BANK_COUNTRY_SEMANTICS } from "../theme/chartTheme";

let worldRegistered = false;
echarts.use([
  BarChart,
  EffectScatterChart,
  GeoComponent,
  GraphChart,
  GridComponent,
  LegendComponent,
  LineChart,
  LinesChart,
  ScatterChart,
  TooltipComponent,
  CanvasRenderer,
]);

function ensureWorldMap() {
  if (worldRegistered) return;
  echarts.registerMap("trailsight-world", worldGeo as never);
  worldRegistered = true;
}

function useChart(option: EChartsCoreOption, registerWorld = false) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (registerWorld) ensureWorldMap();
    const chart = echarts.init(element, undefined, { renderer: "canvas" });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element);
    return () => { observer.disconnect(); chart.dispose(); };
  }, [registerWorld]);
  useEffect(() => {
    const chart = ref.current ? echarts.getInstanceByDom(ref.current) : undefined;
    if (chart) chart.setOption(option, true);
  }, [option]);
  return ref;
}

export function BankCountryRouteMap({ route }: { route: BankCountryRoute }) {
  const { chartTheme } = useTheme();
  const model = useMemo(() => buildRouteVisualModel(route), [route]);
  const option = useMemo<EChartsCoreOption>(() => {
    const sendingGeometryName = getBankCountryMapGeometryName(route.sending.bank_country);
    const receivingGeometryName = getBankCountryMapGeometryName(route.receiving.bank_country);
    const regions = [
      ...(sendingGeometryName ? [{ name: sendingGeometryName, itemStyle: { areaColor: chartTheme.routeSending } }] : []),
      ...(route.same_bank_country || !receivingGeometryName ? [] : [{ name: receivingGeometryName, itemStyle: { areaColor: chartTheme.routeReceiving } }]),
    ];
    const markerData = route.same_bank_country
      ? [{ name: `Sending & receiving · ${route.sending.bank_country}`, value: [...model.sending, 1], bankId: `${route.sending.bank_id} / ${route.receiving.bank_id}` }]
      : [
          { name: `Sending · ${route.sending.bank_country}`, value: [...model.sending, 1], bankId: route.sending.bank_id },
          { name: `Receiving · ${route.receiving.bank_country}`, value: [...model.receiving, 1], bankId: route.receiving.bank_id },
        ];
    return {
      animation: false,
      backgroundColor: chartTheme.chartCanvas,
      tooltip: { trigger: "item", confine: true, backgroundColor: chartTheme.chartTooltipBackground, borderColor: chartTheme.chartTooltipBorder, textStyle: { color: chartTheme.chartTooltipText }, formatter: (params: { data?: { name?: string; bankId?: string } }) => params.data?.bankId ? `${params.data.name}<br/>Bank ${params.data.bankId}` : "Bank Country" },
      geo: { map: "trailsight-world", roam: false, silent: false, itemStyle: { areaColor: chartTheme.mapLand, borderColor: chartTheme.mapBorder, borderWidth: 0.7 }, emphasis: { disabled: true }, regions },
      series: [
        { type: "effectScatter", coordinateSystem: "geo", showEffectOn: "render", rippleEffect: { scale: 2.1, brushType: "stroke" }, symbolSize: 9, itemStyle: { color: chartTheme.routeLine }, data: markerData, z: 4 },
        ...(model.routeLine.length ? [{ type: "lines", coordinateSystem: "geo", data: model.routeLine.map(([from, to]) => ({ coords: [from, to] })), lineStyle: { color: chartTheme.routeLine, width: 2, opacity: 0.95, curveness: 0.22 }, symbol: ["none", "arrow"], symbolSize: 10, z: 3 }] : []),
      ],
    };
  }, [chartTheme, model, route]);
  const ref = useChart(option, true);
  return <div className="visual-block"><div className="route-summary" aria-label="Bank-Country route text summary"><strong>{model.summary}</strong><span>Sending bank {route.sending.bank_id} · Receiving bank {route.receiving.bank_id}</span></div><div ref={ref} className="chart chart--map" role="img" aria-label={`${model.summary}. Bank-country route map using deterministic synthetic bank metadata.`} /><p className="visual-helper">Bank countries are deterministic synthetic metadata added by Trailsight. They are not customer locations.</p></div>;
}

export function AccountBankCountryConnectionsMap({ rootBankCountry, flows }: { rootBankCountry: string; flows: BankCountryFlowRow[] }) {
  const { chartTheme } = useTheme();
  const model = useMemo(() => buildAccountBankCountryVisualModel(rootBankCountry, flows), [rootBankCountry, flows]);
  const option = useMemo<EChartsCoreOption>(() => {
    const rootSameCountryFlow = model.connections.find((connection) => connection.sameCountry);
    const rootTooltip = model.root
      ? rootSameCountryFlow
        ? `Root Bank Country · ${model.root.bank_country}<br/>Same-country incoming: ${rootSameCountryFlow.incomingTransactionCount}<br/>Same-country outgoing: ${rootSameCountryFlow.outgoingTransactionCount}<br/>Distinct counterparties: ${rootSameCountryFlow.distinctCounterparties}<br/>Latest interaction: ${rootSameCountryFlow.latestInteraction}`
        : `Root Bank Country · ${model.root.bank_country}`
      : `Root Bank Country · ${rootBankCountry}`;
    const connectedTooltip = (connection: (typeof model.connections)[number]) =>
      `Connected Bank Country · ${connection.bankCountry}<br/>Incoming transactions: ${connection.incomingTransactionCount}<br/>Outgoing transactions: ${connection.outgoingTransactionCount}<br/>Distinct counterparties: ${connection.distinctCounterparties}<br/>Latest interaction: ${connection.latestInteraction}`;
    const regionTooltips = new Map<string, string>([
      ...(model.rootGeometryName ? [[model.rootGeometryName, rootTooltip] as const] : []),
      ...model.connections.filter((connection) => connection.geometryName).map((connection) => [connection.geometryName!, connection.sameCountry ? rootTooltip : connectedTooltip(connection)] as const),
    ]);
    const regions = [
      ...(model.root && model.rootGeometryName ? [{
        name: model.rootGeometryName,
        itemStyle: { areaColor: chartTheme.mapRoot, borderColor: chartTheme.mapRootBorder, borderWidth: 1.8 },
        emphasis: { itemStyle: { areaColor: chartTheme.mapRootHover, borderColor: chartTheme.mapRootHoverBorder, borderWidth: 2 } },
      }] : []),
      ...model.connections.filter((connection) => connection.geometryName && !connection.sameCountry).map((connection) => ({
        name: connection.geometryName!,
        itemStyle: { areaColor: chartTheme.mapConnected, borderColor: chartTheme.mapConnectedBorder, borderWidth: 1.3 },
        emphasis: { itemStyle: { areaColor: chartTheme.mapConnectedHover, borderColor: chartTheme.mapConnectedHoverBorder, borderWidth: 1.8 } },
      })),
    ];
    const rootMarkerData = model.root ? [{
      name: model.root.bank_country,
      value: [model.root.centroid_longitude, model.root.centroid_latitude, 1],
      tooltipText: rootTooltip,
    }] : [];
    const connectedMarkerData = model.connections.filter((connection) => connection.centroid && !connection.sameCountry).map((connection) => ({
      name: connection.bankCountry,
      value: [connection.centroid!.centroid_longitude, connection.centroid!.centroid_latitude, 1],
      tooltipText: connectedTooltip(connection),
    }));
    const toLineData = (line: (typeof model.incomingLines)[number]) => ({
      name: `${line.direction === "INCOMING" ? "Incoming" : "Outgoing"} · ${line.bankCountry}`,
      coords: [line.from, line.to],
      tooltipText: `${line.direction === "INCOMING" ? "Incoming" : "Outgoing"} · ${line.bankCountry}<br/>Transactions: ${line.transactionCount}<br/>Distinct counterparties: ${line.distinctCounterparties}<br/>Latest interaction: ${line.latestInteraction}`,
    });
    return {
      animation: false,
      backgroundColor: chartTheme.chartCanvas,
      tooltip: {
        trigger: "item",
        confine: true,
        backgroundColor: chartTheme.chartTooltipBackground,
        borderColor: chartTheme.chartTooltipBorder,
        textStyle: { color: chartTheme.chartTooltipText },
        formatter: (params: unknown) => accountBankCountryTooltip(params, regionTooltips),
      },
      geo: {
        map: "trailsight-world",
        roam: true,
        scaleLimit: { min: 1, max: 6 },
        zoom: 1.08,
        layoutCenter: ["50%", "50%"],
        layoutSize: "108%",
        silent: false,
        itemStyle: { areaColor: chartTheme.mapLand, borderColor: chartTheme.mapBorder, borderWidth: 0.7 },
        emphasis: { itemStyle: { areaColor: chartTheme.mapHover }, label: { show: false } },
        regions,
      },
      series: [
        {
          name: ACCOUNT_BANK_COUNTRY_SEMANTICS.root.seriesName,
          type: "scatter",
          coordinateSystem: "geo",
          symbol: "diamond",
          symbolSize: 20,
          itemStyle: { color: chartTheme.mapRootMarker, borderColor: chartTheme.mapRootMarkerBorder, borderWidth: 2 },
          label: { show: true, formatter: "{b}", position: "top", distance: 8, color: chartTheme.mapRootLabel, fontSize: 12, fontWeight: 700, backgroundColor: chartTheme.mapRootLabelBackground, borderColor: chartTheme.mapRootLabelBorder, borderWidth: 1, borderRadius: 3, padding: [4, 6] },
          emphasis: { scale: 1.25 },
          data: rootMarkerData,
          z: 7,
        },
        {
          name: ACCOUNT_BANK_COUNTRY_SEMANTICS.connected.seriesName,
          type: "effectScatter",
          coordinateSystem: "geo",
          showEffectOn: "render",
          rippleEffect: { scale: 2.2, brushType: "stroke" },
          symbolSize: 11,
          itemStyle: { color: chartTheme.mapConnectedMarker, borderColor: chartTheme.mapConnectedMarkerBorder, borderWidth: 1 },
          label: { show: true, formatter: "{b}", position: "right", distance: 6, color: chartTheme.mapConnectedLabel, fontSize: 11, backgroundColor: chartTheme.mapConnectedLabelBackground, borderRadius: 3, padding: [3, 5] },
          emphasis: { scale: 1.3 },
          data: connectedMarkerData,
          z: 6,
        },
        {
          name: ACCOUNT_BANK_COUNTRY_SEMANTICS.outgoing.seriesName,
          type: "lines",
          coordinateSystem: "geo",
          data: model.outgoingLines.map(toLineData),
          lineStyle: { color: chartTheme.flowOutgoing, width: 2.3, opacity: 0.95, curveness: 0.16 },
          emphasis: { lineStyle: { width: 3.4, opacity: 1 } },
          symbol: ["none", "arrow"],
          symbolSize: 11,
          z: 4,
        },
        {
          name: ACCOUNT_BANK_COUNTRY_SEMANTICS.incoming.seriesName,
          type: "lines",
          coordinateSystem: "geo",
          data: model.incomingLines.map(toLineData),
          lineStyle: { color: chartTheme.flowIncoming, width: 2.3, opacity: 0.95, curveness: -0.16 },
          emphasis: { lineStyle: { width: 3.4, opacity: 1 } },
          symbol: ["none", "arrow"],
          symbolSize: 11,
          z: 5,
        },
      ],
    };
  }, [chartTheme, model, rootBankCountry]);
  const ref = useChart(option, true);
  return <div className="visual-block account-country-map">
    <div className="route-summary"><strong>Account Bank-Country Connections</strong><span>{model.summary}</span></div>
    <div ref={ref} className="chart chart--map chart--account-country-map" role="img" aria-label={`Interactive Account Bank-Country connections map. ${model.summary}. Zoom and pan are available.`} />
    <div className="graph-legend account-country-legend" aria-label="Account Bank-Country connection legend">
      <span><i className="legend-country legend-country--root" />{ACCOUNT_BANK_COUNTRY_SEMANTICS.root.legendLabel}</span>
      <span><i className="legend-country legend-country--connected" />{ACCOUNT_BANK_COUNTRY_SEMANTICS.connected.legendLabel}</span>
      <span><i className="legend-line legend-line--outgoing" />{ACCOUNT_BANK_COUNTRY_SEMANTICS.outgoing.legendLabel}</span>
      <span><i className="legend-line legend-line--incoming" />{ACCOUNT_BANK_COUNTRY_SEMANTICS.incoming.legendLabel}</span>
    </div>
    <p className="visual-helper account-country-map__interaction-hint">Interaction: scroll or pinch to zoom, drag to pan, and hover a highlighted country or flow for deterministic details.</p>
    <p className="visual-helper">{model.summary}</p>
    {(!model.root || model.unmappedCountries.length > 0) && <p className="visual-helper">Map marker coordinates are unavailable for {model.root ? model.unmappedCountries.join(", ") : rootBankCountry}; deterministic flow rows remain available in the table below. No safety conclusion is implied.</p>}
    {!!model.polygonUnavailableCountries.length && <p className="visual-helper">Polygon geometry is unavailable for {model.polygonUnavailableCountries.join(", ")}; authoritative centroid markers and flow lines remain visible.</p>}
    <p className="visual-helper">Bank countries are deterministic synthetic metadata added by Trailsight. They are not customer locations.</p>
  </div>;
}

export function AccountRelationshipGraph({ network }: { network: AccountNetwork }) {
  const { chartTheme } = useTheme();
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const option = useMemo<EChartsCoreOption>(() => {
    const nodes = [
      { id: network.root.account_ref, name: `${network.root.bank_id}\n${shortAccount(network.root.account_id)}`, symbolSize: 56, itemStyle: { color: chartTheme.networkRootFill, borderColor: chartTheme.networkRootBorder, borderWidth: 3 }, label: { show: true, color: chartTheme.networkRootLabel, fontSize: 11 }, bankCountry: network.root.bank_country },
      ...network.counterparties.map((node) => ({ id: node.account_ref, name: `${node.bank_id}\n${shortAccount(node.account_id)}`, symbolSize: selectedNode === node.account_ref ? 38 : 33, itemStyle: { color: selectedNode === node.account_ref ? chartTheme.networkCounterpartySelectedFill : chartTheme.networkCounterpartyFill, borderColor: selectedNode === node.account_ref ? chartTheme.networkCounterpartySelectedBorder : chartTheme.networkCounterpartyBorder, borderWidth: selectedNode === node.account_ref ? 2 : 1 }, label: { show: true, color: chartTheme.networkCounterpartyLabel, fontSize: 10 }, bankCountry: node.bank_country })),
    ];
    const links: Array<Record<string, unknown>> = [];
    for (const relationship of network.relationships) {
      if (relationship.outgoing_count > 0) links.push({ source: network.root.account_ref, target: relationship.counterparty_account_ref, count: relationship.outgoing_count, direction: "Outgoing", selected: relationship.selected_relationship, lineStyle: { width: relationship.selected_relationship ? 3 : 1.2, color: relationship.selected_relationship ? chartTheme.networkEdgeSelected : chartTheme.networkEdgeOutgoing, curveness: relationship.incoming_count ? 0.13 : 0.05 } });
      if (relationship.incoming_count > 0) links.push({ source: relationship.counterparty_account_ref, target: network.root.account_ref, count: relationship.incoming_count, direction: "Incoming", selected: relationship.selected_relationship, lineStyle: { width: relationship.selected_relationship ? 3 : 1.2, color: relationship.selected_relationship ? chartTheme.networkEdgeSelected : chartTheme.networkEdgeIncoming, curveness: relationship.outgoing_count ? -0.13 : -0.05 } });
    }
    return { animation: false, backgroundColor: chartTheme.chartCanvas, tooltip: { backgroundColor: chartTheme.chartTooltipBackground, borderColor: chartTheme.chartTooltipBorder, textStyle: { color: chartTheme.chartTooltipText }, formatter: (params: { dataType?: string; data?: { name?: string; bankCountry?: string; direction?: string; count?: number; selected?: boolean } }) => params.dataType === "edge" ? `${params.data?.direction}: ${params.data?.count} transaction(s)${params.data?.selected ? "<br/>Selected transaction relationship" : ""}` : `${params.data?.name?.replace("\n", " / ")}<br/>Bank Country: ${params.data?.bankCountry ?? "—"}` }, series: [{ type: "graph", layout: "circular", circular: { rotateLabel: false }, roam: false, data: nodes, links, edgeSymbol: ["none", "arrow"], edgeSymbolSize: [0, 8], lineStyle: { opacity: 0.78 }, emphasis: { focus: "adjacency" } }] };
  }, [chartTheme, network, selectedNode]);
  const ref = useChart(option);
  useEffect(() => {
    const chart = ref.current ? echarts.getInstanceByDom(ref.current) : undefined;
    if (!chart) return;
    const handler = (params: ECElementEvent) => {
      if (params.dataType !== "node") return;
      const data = params.data;
      if (!data || typeof data !== "object" || Array.isArray(data) || !("id" in data)) return;
      const nodeId = data.id;
      if (typeof nodeId !== "string" || nodeId === network.root.account_ref) return;
      setSelectedNode(nodeId);
    };
    chart.on("click", handler);
    return () => { if (!chart.isDisposed()) chart.off("click", handler); };
  }, [network.root.account_ref, ref, selectedNode]);
  const truncation = graphTruncationText(network);
  return <div className="visual-block"><div ref={ref} className="chart chart--graph" role="img" aria-label={`One-hop account relationship graph. Root account ${network.root.bank_id} ${network.root.account_id}. ${network.shown_counterparties} direct counterparties shown.`} /><div className="graph-legend"><span><i className="legend-line legend-line--selected" />Selected transaction</span><span>Arrows show transaction direction</span><span>One hop only · no expansion</span></div>{truncation && <p className="visual-helper">{truncation}</p>}</div>;
}

export function ActivityTimeline({ activity }: { activity: ActivityContext }) {
  const { chartTheme } = useTheme();
  const currencies = useMemo(() => activityCurrencies(activity), [activity]);
  const [currency, setCurrency] = useState(() => activity.selected_transaction?.currency ?? currencies[0] ?? "");
  useEffect(() => { const preferred = activity.selected_transaction?.currency; setCurrency(preferred && currencies.includes(preferred) ? preferred : currencies[0] ?? ""); }, [activity, currencies]);
  const buckets = useMemo(() => activityBucketsForCurrency(activity, currency), [activity, currency]);
  const option = useMemo<EChartsCoreOption>(() => ({
    animation: false, backgroundColor: chartTheme.chartCanvas, grid: { left: 64, right: 58, top: 28, bottom: 52 }, tooltip: { trigger: "axis", backgroundColor: chartTheme.chartTooltipBackground, borderColor: chartTheme.chartTooltipBorder, textStyle: { color: chartTheme.chartTooltipText } }, legend: { top: 0, textStyle: { color: chartTheme.chartLabel }, data: ["Incoming amount", "Outgoing amount", "Transaction count"] },
    xAxis: { type: "category", data: buckets.map(activityBucketAxisValue), axisLabel: { color: chartTheme.chartAxis, formatter: (value: string) => value.slice(5, 24).replace("T", " ").replace("|", " · ") }, axisLine: { lineStyle: { color: chartTheme.chartAxisLine } } },
    yAxis: [{ type: "value", name: currency ? `Amount · ${currency}` : "Amount", nameTextStyle: { color: chartTheme.chartAxis }, axisLabel: { color: chartTheme.chartAxis }, splitLine: { lineStyle: { color: chartTheme.chartGrid } } }, { type: "value", name: "Count", nameTextStyle: { color: chartTheme.chartAxis }, axisLabel: { color: chartTheme.chartAxis }, splitLine: { show: false } }],
    series: [
      { name: "Incoming amount", type: "line", symbolSize: 5, data: buckets.map((bucket) => Number(bucket.incoming_amount)), lineStyle: { color: chartTheme.seriesIncoming }, itemStyle: { color: chartTheme.seriesIncoming } },
      { name: "Outgoing amount", type: "line", symbolSize: 5, data: buckets.map((bucket) => Number(bucket.outgoing_amount)), lineStyle: { color: chartTheme.seriesOutgoing }, itemStyle: { color: chartTheme.seriesOutgoing } },
      { name: "Transaction count", type: "bar", yAxisIndex: 1, data: buckets.map((bucket) => bucket.transaction_count), itemStyle: { color: chartTheme.seriesCount, opacity: 0.65 }, barMaxWidth: 18 },
    ],
  }), [buckets, chartTheme, currency]);
  const ref = useChart(option);
  return <div className="visual-block"><div className="chart-toolbar"><span className="chart-summary">Amounts are never summed across unlike currencies.</span>{currencies.length > 1 && <label className="field field--inline"><span>Currency</span><select value={currency} onChange={(event) => setCurrency(event.target.value)}>{currencies.map((item) => <option key={item}>{item}</option>)}</select></label>}</div><div ref={ref} className="chart chart--timeline" role="img" aria-label={`Account activity timeline for ${currency}. Incoming and outgoing amounts use ${currency}; transaction counts use a separate axis.`} /><p className="visual-helper">Text summary: {buckets.length} time buckets shown for {currency || "the selected currency"}; incoming amount, outgoing amount, and transaction count remain separate measures.</p></div>;
}

export function CompactBars({ rows, ariaLabel }: { rows: Array<{ label: string; incoming: number; outgoing: number }>; ariaLabel: string }) {
  const { chartTheme } = useTheme();
  const option = useMemo<EChartsCoreOption>(() => ({ animation: false, backgroundColor: chartTheme.chartCanvas, grid: { left: 72, right: 24, top: 20, bottom: 36 }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: chartTheme.chartTooltipBackground, borderColor: chartTheme.chartTooltipBorder, textStyle: { color: chartTheme.chartTooltipText } }, legend: { top: 0, textStyle: { color: chartTheme.chartLabel } }, xAxis: { type: "value", axisLabel: { color: chartTheme.chartAxis }, splitLine: { lineStyle: { color: chartTheme.chartGrid } } }, yAxis: { type: "category", data: rows.map((row) => row.label), axisLabel: { color: chartTheme.chartLabel }, axisLine: { lineStyle: { color: chartTheme.chartAxisLine } } }, series: [{ name: "Incoming", type: "bar", data: rows.map((row) => row.incoming), itemStyle: { color: chartTheme.seriesIncoming } }, { name: "Outgoing", type: "bar", data: rows.map((row) => row.outgoing), itemStyle: { color: chartTheme.seriesOutgoing } }] }), [chartTheme, rows]);
  const ref = useChart(option);
  return <div className="visual-block"><div ref={ref} className="chart chart--compact" role="img" aria-label={ariaLabel} /><p className="visual-helper">{rows.map((row) => `${row.label}: ${row.incoming} incoming, ${row.outgoing} outgoing`).join(" · ")}</p></div>;
}

function activityBucketAxisValue(bucket: ActivityContext["buckets"][number]) { return bucket.direction ? `${bucket.timestamp}|${bucket.direction === "INCOMING" ? "IN" : "OUT"}` : bucket.timestamp; }

function shortAccount(value: string) { return value.length > 9 ? `${value.slice(0, 6)}…` : value; }
