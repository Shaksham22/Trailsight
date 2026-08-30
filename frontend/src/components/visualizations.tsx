import { useEffect, useMemo, useRef, useState } from "react";
import * as echarts from "echarts";
import worldGeo from "../assets/world.geo.json";
import type { AccountNetwork, ActivityContext, BankCountryFlowRow, BankCountryRoute } from "../api/types";
import { activityBucketsForCurrency, activityCurrencies, buildAccountBankCountryVisualModel, buildRouteVisualModel, graphTruncationText } from "../lib/visualization";

let worldRegistered = false;
function ensureWorldMap() {
  if (worldRegistered) return;
  echarts.registerMap("trailsight-world", worldGeo as never);
  worldRegistered = true;
}

function useChart(option: echarts.EChartsCoreOption, registerWorld = false) {
  const ref = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (registerWorld) ensureWorldMap();
    const chart = echarts.init(element, undefined, { renderer: "canvas" });
    chart.setOption(option, true);
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(element);
    return () => { observer.disconnect(); chart.dispose(); };
  }, [option, registerWorld]);
  return ref;
}

export function BankCountryRouteMap({ route }: { route: BankCountryRoute }) {
  const model = useMemo(() => buildRouteVisualModel(route), [route]);
  const option = useMemo<echarts.EChartsCoreOption>(() => {
    const regions = [
      { name: route.sending.bank_country, itemStyle: { areaColor: "#4DB7E5" } },
      ...(route.same_bank_country ? [] : [{ name: route.receiving.bank_country, itemStyle: { areaColor: "#9A8CFF" } }]),
    ];
    const markerData = route.same_bank_country
      ? [{ name: `Sending & receiving · ${route.sending.bank_country}`, value: [...model.sending, 1], bankId: `${route.sending.bank_id} / ${route.receiving.bank_id}` }]
      : [
          { name: `Sending · ${route.sending.bank_country}`, value: [...model.sending, 1], bankId: route.sending.bank_id },
          { name: `Receiving · ${route.receiving.bank_country}`, value: [...model.receiving, 1], bankId: route.receiving.bank_id },
        ];
    return {
      animation: false,
      tooltip: { trigger: "item", confine: true, backgroundColor: "#0A1624", borderColor: "#2A4A62", textStyle: { color: "#F3F7FA" }, formatter: (params: { data?: { name?: string; bankId?: string } }) => params.data?.bankId ? `${params.data.name}<br/>Bank ${params.data.bankId}` : "Bank Country" },
      geo: { map: "trailsight-world", roam: false, silent: false, itemStyle: { areaColor: "#122334", borderColor: "#294156", borderWidth: 0.7 }, emphasis: { disabled: true }, regions },
      series: [
        { type: "effectScatter", coordinateSystem: "geo", showEffectOn: "render", rippleEffect: { scale: 2.1, brushType: "stroke" }, symbolSize: 9, itemStyle: { color: "#6CC8EE" }, data: markerData, z: 4 },
        ...(model.routeLine.length ? [{ type: "lines", coordinateSystem: "geo", data: model.routeLine.map(([from, to]) => ({ coords: [from, to] })), lineStyle: { color: "#6CC8EE", width: 2, opacity: 0.95, curveness: 0.22 }, symbol: ["none", "arrow"], symbolSize: 10, z: 3 }] : []),
      ],
    };
  }, [model, route]);
  const ref = useChart(option, true);
  return <div className="visual-block"><div className="route-summary" aria-label="Bank-Country route text summary"><strong>{model.summary}</strong><span>Sending bank {route.sending.bank_id} · Receiving bank {route.receiving.bank_id}</span></div><div ref={ref} className="chart chart--map" role="img" aria-label={`${model.summary}. Bank-country route map using deterministic synthetic bank metadata.`} /><p className="visual-helper">Bank countries are deterministic synthetic metadata added by Trailsight. They are not customer locations.</p></div>;
}

export function AccountBankCountryConnectionsMap({ rootBankCountry, flows }: { rootBankCountry: string; flows: BankCountryFlowRow[] }) {
  const model = useMemo(() => buildAccountBankCountryVisualModel(rootBankCountry, flows), [rootBankCountry, flows]);
  const option = useMemo<echarts.EChartsCoreOption>(() => {
    const rootSameCountryFlow = model.connections.find((connection) => connection.sameCountry);
    const rootTooltip = model.root
      ? rootSameCountryFlow
        ? `Root Bank Country · ${model.root.bank_country}<br/>Same-country incoming: ${rootSameCountryFlow.incomingTransactionCount}<br/>Same-country outgoing: ${rootSameCountryFlow.outgoingTransactionCount}<br/>Distinct counterparties: ${rootSameCountryFlow.distinctCounterparties}<br/>Latest interaction: ${rootSameCountryFlow.latestInteraction}`
        : `Root Bank Country · ${model.root.bank_country}`
      : `Root Bank Country · ${rootBankCountry}`;
    const connectedTooltip = (connection: (typeof model.connections)[number]) =>
      `Connected Bank Country · ${connection.bankCountry}<br/>Incoming transactions: ${connection.incomingTransactionCount}<br/>Outgoing transactions: ${connection.outgoingTransactionCount}<br/>Distinct counterparties: ${connection.distinctCounterparties}<br/>Latest interaction: ${connection.latestInteraction}`;
    const regionTooltips = new Map<string, string>([
      ...(model.root ? [[model.root.bank_country, rootTooltip] as const] : []),
      ...model.connections.map((connection) => [connection.bankCountry, connection.sameCountry ? rootTooltip : connectedTooltip(connection)] as const),
    ]);
    const regions = [
      ...(model.root ? [{
        name: model.root.bank_country,
        itemStyle: { areaColor: "#D7B95B", borderColor: "#FFF0A8", borderWidth: 1.8 },
        emphasis: { itemStyle: { areaColor: "#E7C968", borderColor: "#FFF6CA", borderWidth: 2 } },
      }] : []),
      ...model.connections.filter((connection) => connection.centroid && !connection.sameCountry).map((connection) => ({
        name: connection.bankCountry,
        itemStyle: { areaColor: "#287E98", borderColor: "#76D5EA", borderWidth: 1.3 },
        emphasis: { itemStyle: { areaColor: "#3298B4", borderColor: "#A2ECFB", borderWidth: 1.8 } },
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
      tooltip: {
        trigger: "item",
        confine: true,
        backgroundColor: "#0A1624",
        borderColor: "#2A4A62",
        textStyle: { color: "#F3F7FA" },
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
        itemStyle: { areaColor: "#122334", borderColor: "#294156", borderWidth: 0.7 },
        emphasis: { itemStyle: { areaColor: "#1B354A" }, label: { show: false } },
        regions,
      },
      series: [
        {
          name: "Root Bank Country",
          type: "scatter",
          coordinateSystem: "geo",
          symbol: "diamond",
          symbolSize: 20,
          itemStyle: { color: "#F1D06B", borderColor: "#FFF5C4", borderWidth: 2 },
          label: { show: true, formatter: "{b}", position: "top", distance: 8, color: "#FFF4BE", fontSize: 12, fontWeight: 700, backgroundColor: "rgba(7,17,29,.88)", borderColor: "#6E5E30", borderWidth: 1, borderRadius: 3, padding: [4, 6] },
          emphasis: { scale: 1.25 },
          data: rootMarkerData,
          z: 7,
        },
        {
          name: "Connected Bank Countries",
          type: "effectScatter",
          coordinateSystem: "geo",
          showEffectOn: "render",
          rippleEffect: { scale: 2.2, brushType: "stroke" },
          symbolSize: 11,
          itemStyle: { color: "#69D0E7", borderColor: "#C5F4FF", borderWidth: 1 },
          label: { show: true, formatter: "{b}", position: "right", distance: 6, color: "#BFEAF4", fontSize: 11, backgroundColor: "rgba(7,17,29,.82)", borderRadius: 3, padding: [3, 5] },
          emphasis: { scale: 1.3 },
          data: connectedMarkerData,
          z: 6,
        },
        {
          name: "Outgoing",
          type: "lines",
          coordinateSystem: "geo",
          data: model.outgoingLines.map(toLineData),
          lineStyle: { color: "#B69CFF", width: 2.3, opacity: 0.95, curveness: 0.16 },
          emphasis: { lineStyle: { width: 3.4, opacity: 1 } },
          symbol: ["none", "arrow"],
          symbolSize: 11,
          z: 4,
        },
        {
          name: "Incoming",
          type: "lines",
          coordinateSystem: "geo",
          data: model.incomingLines.map(toLineData),
          lineStyle: { color: "#67D3A5", width: 2.3, opacity: 0.95, curveness: -0.16 },
          emphasis: { lineStyle: { width: 3.4, opacity: 1 } },
          symbol: ["none", "arrow"],
          symbolSize: 11,
          z: 5,
        },
      ],
    };
  }, [model, rootBankCountry]);
  const ref = useChart(option, true);
  const unavailable = !model.root || model.unmappedCountries.length > 0;
  return <div className="visual-block account-country-map">
    <div className="route-summary"><strong>Account Bank-Country Connections</strong><span>{model.summary}</span></div>
    <div ref={ref} className="chart chart--map chart--account-country-map" role="img" aria-label={`Interactive Account Bank-Country connections map. ${model.summary}. Zoom and pan are available.`} />
    <div className="graph-legend account-country-legend" aria-label="Account Bank-Country connection legend">
      <span><i className="legend-country legend-country--root" />Root Bank Country</span>
      <span><i className="legend-country legend-country--connected" />Connected Bank Country</span>
      <span><i className="legend-line legend-line--outgoing" />Outgoing account activity</span>
      <span><i className="legend-line legend-line--incoming" />Incoming account activity</span>
    </div>
    <p className="visual-helper account-country-map__interaction-hint">Interaction: scroll or pinch to zoom, drag to pan, and hover a highlighted country or flow for deterministic details.</p>
    <p className="visual-helper">{model.summary}</p>
    {unavailable && <p className="visual-helper">Map geometry is unavailable for {model.root ? model.unmappedCountries.join(", ") : rootBankCountry}; deterministic flow rows remain available in the table below. No safety conclusion is implied.</p>}
    <p className="visual-helper">Bank countries are deterministic synthetic metadata added by Trailsight. They are not customer locations.</p>
  </div>;
}

export function AccountRelationshipGraph({ network }: { network: AccountNetwork }) {
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const option = useMemo<echarts.EChartsCoreOption>(() => {
    const nodes = [
      { id: network.root.account_ref, name: `${network.root.bank_id}\n${shortAccount(network.root.account_id)}`, symbolSize: 56, itemStyle: { color: "#102235", borderColor: "#58BCEB", borderWidth: 3 }, label: { show: true, color: "#F3F7FA", fontSize: 11 }, bankCountry: network.root.bank_country },
      ...network.counterparties.map((node) => ({ id: node.account_ref, name: `${node.bank_id}\n${shortAccount(node.account_id)}`, symbolSize: selectedNode === node.account_ref ? 38 : 33, itemStyle: { color: selectedNode === node.account_ref ? "#173A4F" : "#122334", borderColor: selectedNode === node.account_ref ? "#79D5FF" : "#2A4A62", borderWidth: selectedNode === node.account_ref ? 2 : 1 }, label: { show: true, color: "#B9C7D3", fontSize: 10 }, bankCountry: node.bank_country })),
    ];
    const links: Array<Record<string, unknown>> = [];
    for (const relationship of network.relationships) {
      if (relationship.outgoing_count > 0) links.push({ source: network.root.account_ref, target: relationship.counterparty_account_ref, count: relationship.outgoing_count, direction: "Outgoing", selected: relationship.selected_relationship, lineStyle: { width: relationship.selected_relationship ? 3 : 1.2, color: relationship.selected_relationship ? "#79D5FF" : "#4D7A96", curveness: relationship.incoming_count ? 0.13 : 0.05 } });
      if (relationship.incoming_count > 0) links.push({ source: relationship.counterparty_account_ref, target: network.root.account_ref, count: relationship.incoming_count, direction: "Incoming", selected: relationship.selected_relationship, lineStyle: { width: relationship.selected_relationship ? 3 : 1.2, color: relationship.selected_relationship ? "#79D5FF" : "#7F8CFF", curveness: relationship.outgoing_count ? -0.13 : -0.05 } });
    }
    return { animation: false, tooltip: { backgroundColor: "#0A1624", borderColor: "#2A4A62", textStyle: { color: "#F3F7FA" }, formatter: (params: { dataType?: string; data?: { name?: string; bankCountry?: string; direction?: string; count?: number; selected?: boolean } }) => params.dataType === "edge" ? `${params.data?.direction}: ${params.data?.count} transaction(s)${params.data?.selected ? "<br/>Selected transaction relationship" : ""}` : `${params.data?.name?.replace("\n", " / ")}<br/>Bank Country: ${params.data?.bankCountry ?? "—"}` }, series: [{ type: "graph", layout: "circular", circular: { rotateLabel: false }, roam: false, data: nodes, links, edgeSymbol: ["none", "arrow"], edgeSymbolSize: [0, 8], lineStyle: { opacity: 0.78 }, emphasis: { focus: "adjacency" } }] };
  }, [network, selectedNode]);
  const ref = useChart(option);
  useEffect(() => {
    const chart = ref.current ? echarts.getInstanceByDom(ref.current) : undefined;
    if (!chart) return;
    const handler = (params: echarts.ECElementEvent) => {
      if (params.dataType !== "node") return;
      const data = params.data;
      if (!data || typeof data !== "object" || Array.isArray(data) || !("id" in data)) return;
      const nodeId = data.id;
      if (typeof nodeId !== "string" || nodeId === network.root.account_ref) return;
      setSelectedNode(nodeId);
    };
    chart.on("click", handler);
    return () => { chart.off("click", handler); };
  }, [network.root.account_ref, ref, selectedNode]);
  const truncation = graphTruncationText(network);
  return <div className="visual-block"><div ref={ref} className="chart chart--graph" role="img" aria-label={`One-hop account relationship graph. Root account ${network.root.bank_id} ${network.root.account_id}. ${network.shown_counterparties} direct counterparties shown.`} /><div className="graph-legend"><span><i className="legend-line legend-line--selected" />Selected transaction</span><span>Arrows show transaction direction</span><span>One hop only · no expansion</span></div>{truncation && <p className="visual-helper">{truncation}</p>}</div>;
}

export function ActivityTimeline({ activity }: { activity: ActivityContext }) {
  const currencies = useMemo(() => activityCurrencies(activity), [activity]);
  const [currency, setCurrency] = useState(() => activity.selected_transaction?.currency ?? currencies[0] ?? "");
  useEffect(() => { const preferred = activity.selected_transaction?.currency; setCurrency(preferred && currencies.includes(preferred) ? preferred : currencies[0] ?? ""); }, [activity, currencies]);
  const buckets = useMemo(() => activityBucketsForCurrency(activity, currency), [activity, currency]);
  const option = useMemo<echarts.EChartsCoreOption>(() => ({
    animation: false, grid: { left: 64, right: 58, top: 28, bottom: 52 }, tooltip: { trigger: "axis", backgroundColor: "#0A1624", borderColor: "#2A4A62", textStyle: { color: "#F3F7FA" } }, legend: { top: 0, textStyle: { color: "#B9C7D3" }, data: ["Incoming amount", "Outgoing amount", "Transaction count"] },
    xAxis: { type: "category", data: buckets.map(activityBucketAxisValue), axisLabel: { color: "#7F94A6", formatter: (value: string) => value.slice(5, 24).replace("T", " ").replace("|", " · ") }, axisLine: { lineStyle: { color: "#294156" } } },
    yAxis: [{ type: "value", name: currency ? `Amount · ${currency}` : "Amount", nameTextStyle: { color: "#7F94A6" }, axisLabel: { color: "#7F94A6" }, splitLine: { lineStyle: { color: "#1C3448" } } }, { type: "value", name: "Count", nameTextStyle: { color: "#7F94A6" }, axisLabel: { color: "#7F94A6" }, splitLine: { show: false } }],
    series: [
      { name: "Incoming amount", type: "line", symbolSize: 5, data: buckets.map((bucket) => Number(bucket.incoming_amount)), lineStyle: { color: "#55C7E8" }, itemStyle: { color: "#55C7E8" } },
      { name: "Outgoing amount", type: "line", symbolSize: 5, data: buckets.map((bucket) => Number(bucket.outgoing_amount)), lineStyle: { color: "#9A8CFF" }, itemStyle: { color: "#9A8CFF" } },
      { name: "Transaction count", type: "bar", yAxisIndex: 1, data: buckets.map((bucket) => bucket.transaction_count), itemStyle: { color: "#415D73", opacity: 0.65 }, barMaxWidth: 18 },
    ],
  }), [buckets, currency]);
  const ref = useChart(option);
  return <div className="visual-block"><div className="chart-toolbar"><span className="chart-summary">Amounts are never summed across unlike currencies.</span>{currencies.length > 1 && <label className="field field--inline"><span>Currency</span><select value={currency} onChange={(event) => setCurrency(event.target.value)}>{currencies.map((item) => <option key={item}>{item}</option>)}</select></label>}</div><div ref={ref} className="chart chart--timeline" role="img" aria-label={`Account activity timeline for ${currency}. Incoming and outgoing amounts use ${currency}; transaction counts use a separate axis.`} /><p className="visual-helper">Text summary: {buckets.length} time buckets shown for {currency || "the selected currency"}; incoming amount, outgoing amount, and transaction count remain separate measures.</p></div>;
}

export function CompactBars({ rows, ariaLabel }: { rows: Array<{ label: string; incoming: number; outgoing: number }>; ariaLabel: string }) {
  const option = useMemo<echarts.EChartsCoreOption>(() => ({ animation: false, grid: { left: 72, right: 24, top: 20, bottom: 36 }, tooltip: { trigger: "axis", axisPointer: { type: "shadow" }, backgroundColor: "#0A1624", borderColor: "#2A4A62", textStyle: { color: "#F3F7FA" } }, legend: { top: 0, textStyle: { color: "#B9C7D3" } }, xAxis: { type: "value", axisLabel: { color: "#7F94A6" }, splitLine: { lineStyle: { color: "#1C3448" } } }, yAxis: { type: "category", data: rows.map((row) => row.label), axisLabel: { color: "#B9C7D3" }, axisLine: { lineStyle: { color: "#294156" } } }, series: [{ name: "Incoming", type: "bar", data: rows.map((row) => row.incoming), itemStyle: { color: "#55C7E8" } }, { name: "Outgoing", type: "bar", data: rows.map((row) => row.outgoing), itemStyle: { color: "#9A8CFF" } }] }), [rows]);
  const ref = useChart(option);
  return <div className="visual-block"><div ref={ref} className="chart chart--compact" role="img" aria-label={ariaLabel} /><p className="visual-helper">{rows.map((row) => `${row.label}: ${row.incoming} incoming, ${row.outgoing} outgoing`).join(" · ")}</p></div>;
}

function activityBucketAxisValue(bucket: ActivityContext["buckets"][number]) { return bucket.direction ? `${bucket.timestamp}|${bucket.direction === "INCOMING" ? "IN" : "OUT"}` : bucket.timestamp; }

function shortAccount(value: string) { return value.length > 9 ? `${value.slice(0, 6)}…` : value; }


function accountBankCountryTooltip(params: unknown, regionTooltips: ReadonlyMap<string, string>): string {
  if (!params || typeof params !== "object" || Array.isArray(params)) return "Bank Country";
  if ("data" in params) {
    const data = params.data;
    if (data && typeof data === "object" && !Array.isArray(data) && "tooltipText" in data && typeof data.tooltipText === "string") return data.tooltipText;
  }
  if ("name" in params && typeof params.name === "string") return regionTooltips.get(params.name) ?? params.name;
  return "Bank Country";
}
