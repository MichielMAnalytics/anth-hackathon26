import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import "leaflet.heat";
import { fetchMessages } from "../../lib/api";
import { useStore } from "../../lib/store";
import type { Incident, Message, Region, Severity } from "../../lib/types";

const REGION_ZOOM = 10;
const MESSAGE_DOT_MIN_ZOOM = 9; // show individual messages when zoomed in
const WORLD_VIEW: L.LatLngExpression = [30, 40];
const WORLD_ZOOM = 4;

// Cinematic flyTo defaults — longer duration + lower easeLinearity for a
// smoother, less abrupt zoom-in feel.
const FLY_OPTS_INITIAL = { duration: 1.8, easeLinearity: 0.15 } as const;
const FLY_OPTS_REGION = { duration: 1.1, easeLinearity: 0.2 } as const;

const SEV_COLOR: Record<Severity, string> = {
  critical: "#9b4a3a",
  high: "#b07636",
  medium: "#b4943f",
  low: "#6a8957",
};

declare module "leaflet" {
  function heatLayer(latlngs: [number, number, number?][], options?: object): L.Layer;
}

export function IncidentMap() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);
  const heatLayerRef = useRef<L.Layer | null>(null);
  const markersLayerRef = useRef<L.LayerGroup | null>(null);
  const messagesLayerRef = useRef<L.LayerGroup | null>(null);

  const incidents = useStore((s) => s.incidents);
  const regions = useStore((s) => s.regions);
  const selectedRegion = useStore((s) => s.selectedRegion);
  const selectRegion = useStore((s) => s.selectRegion);
  const issueFilter = useStore((s) => s.issueFilter);
  const didInitialFit = useRef(false);
  const [zoom, setZoom] = useState(WORLD_ZOOM);
  const [messagesByIncident, setMessagesByIncident] = useState<
    Record<string, Message[]>
  >({});

  // initialize once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      zoomControl: true,
      attributionControl: false,
      zoomSnap: 0.25,
      zoomDelta: 0.5,
      wheelDebounceTime: 40,
      wheelPxPerZoomLevel: 90,
      inertia: true,
    }).setView(WORLD_VIEW, WORLD_ZOOM);

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 19,
        subdomains: "abcd",
      },
    ).addTo(map);

    L.control
      .attribution({ prefix: false })
      .addAttribution("© OpenStreetMap · CARTO")
      .addTo(map);

    mapRef.current = map;
    markersLayerRef.current = L.layerGroup().addTo(map);
    messagesLayerRef.current = L.layerGroup().addTo(map);

    setZoom(map.getZoom());
    map.on("zoomend", () => setZoom(map.getZoom()));

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // when zoomed in, fetch & cache messages for visible incidents (those in
  // selected region or all if no region picked)
  useEffect(() => {
    if (zoom < MESSAGE_DOT_MIN_ZOOM) return;
    const wanted = Object.values(incidents).filter((i) => {
      if (issueFilter !== "all" && i.category !== issueFilter) return false;
      if (selectedRegion === "all") return true;
      return i.region === selectedRegion;
    });
    wanted.forEach((inc) => {
      if (messagesByIncident[inc.id]) return;
      fetchMessages(inc.id)
        .then((msgs) =>
          setMessagesByIncident((prev) =>
            prev[inc.id] ? prev : { ...prev, [inc.id]: msgs },
          ),
        )
        .catch(() => {});
    });
  }, [zoom, incidents, selectedRegion, issueFilter, messagesByIncident]);

  // points for heatmap (one per incident, weighted by message count)
  const heatPoints = useMemo<[number, number, number][]>(() => {
    return Object.values(incidents)
      .filter(
        (i): i is Incident & { lat: number; lon: number } =>
          typeof i.lat === "number" && typeof i.lon === "number",
      )
      .filter((i) => issueFilter === "all" || i.category === issueFilter)
      .map((i) => [i.lat, i.lon, Math.min(1, 0.2 + i.messageCount * 0.15)]);
  }, [incidents, issueFilter]);

  // refresh heat + markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current);
    }
    if (heatPoints.length > 0) {
      heatLayerRef.current = L.heatLayer(heatPoints, {
        radius: 28,
        blur: 22,
        maxZoom: 8,
        gradient: {
          0.2: "#cbd9c4",
          0.4: "#c8b18a",
          0.6: "#b07636",
          0.85: "#9b4a3a",
        },
      }).addTo(map);
    }

    const group = markersLayerRef.current!;
    group.clearLayers();

    Object.values(incidents).forEach((inc) => {
      if (typeof inc.lat !== "number" || typeof inc.lon !== "number") return;
      if (issueFilter !== "all" && inc.category !== issueFilter) return;
      const r = 6 + Math.min(18, inc.messageCount * 3);
      const c = L.circleMarker([inc.lat, inc.lon], {
        radius: r,
        color: SEV_COLOR[inc.severity],
        fillColor: SEV_COLOR[inc.severity],
        fillOpacity: 0.32,
        weight: 1.5,
      })
        .bindTooltip(
          `<div style="font-family: 'Fraunces', serif; font-size: 13px; color: #221f18; margin-bottom: 2px;">${inc.title}</div>` +
            `<div style="font-size: 11px; color: #6e6552;">${inc.messageCount} message${inc.messageCount === 1 ? "" : "s"} · ${inc.severity}</div>`,
          { direction: "top", offset: [0, -2], className: "ngo-tip" },
        )
        .on("click", () => {
          selectRegion(inc.region);
          map.flyTo(
            [inc.lat as number, inc.lon as number],
            REGION_ZOOM,
            FLY_OPTS_REGION,
          );
        });
      group.addLayer(c);
    });

    // individual message dots — only at zoom >= MESSAGE_DOT_MIN_ZOOM
    const mGroup = messagesLayerRef.current!;
    mGroup.clearLayers();
    if (zoom >= MESSAGE_DOT_MIN_ZOOM) {
      const visibleIncidents = Object.values(incidents).filter((i) => {
        if (issueFilter !== "all" && i.category !== issueFilter) return false;
        if (selectedRegion === "all") return true;
        return i.region === selectedRegion;
      });
      visibleIncidents.forEach((inc) => {
        const msgs = messagesByIncident[inc.id];
        if (!msgs) return;
        const color = SEV_COLOR[inc.severity];
        msgs.forEach((m) => {
          if (typeof m.lat !== "number" || typeof m.lon !== "number") return;
          if (m.outbound) return; // only inbound civilian dots on map
          const distress = !!m.extracted?.distress;
          const dot = L.circleMarker([m.lat, m.lon], {
            radius: distress ? 3.5 : 2.5,
            color,
            weight: distress ? 1 : 0.5,
            opacity: distress ? 0.9 : 0.45,
            fillColor: color,
            fillOpacity: distress ? 0.55 : 0.32,
            interactive: true,
          }).bindTooltip(
            `<div style="font-size: 11px; color: #475569; max-width: 260px;">` +
              `<div style="font-family: 'JetBrains Mono', monospace; color: #94a3b8;">` +
              `···${m.from.slice(-4)} · ${new Date(m.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` +
              `</div>` +
              `<div style="margin-top: 2px; color: #0f172a; line-height: 1.35;">` +
              m.body.replace(/[<>]/g, "").slice(0, 140) +
              (m.body.length > 140 ? "…" : "") +
              `</div></div>`,
            { direction: "top", offset: [0, -2], className: "ngo-tip" },
          );
          mGroup.addLayer(dot);
        });
      });
    }

    // also region centroid markers (small, neutral)
    Object.values(regions).forEach((rs) => {
      const c = L.circleMarker([rs.lat, rs.lon], {
        radius: 4,
        color: "#534b3d",
        fillColor: "#fbfaf6",
        fillOpacity: 1,
        weight: 1,
      })
        .bindTooltip(rs.label, { direction: "top", offset: [0, -2] })
        .on("click", () => {
          selectRegion(rs.region);
          map.flyTo([rs.lat, rs.lon], REGION_ZOOM, FLY_OPTS_REGION);
        });
      group.addLayer(c);
    });
  }, [
    heatPoints,
    incidents,
    regions,
    selectRegion,
    selectedRegion,
    issueFilter,
    zoom,
    messagesByIncident,
  ]);

  // react to selectedRegion changes (FilterBar, panel selection, etc.)
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (selectedRegion === "all") return; // user explicitly chose all
    const meta = regions[selectedRegion as Region];
    if (!meta) return;
    map.flyTo([meta.lat, meta.lon], REGION_ZOOM, FLY_OPTS_REGION);
  }, [selectedRegion, regions]);

  // on first load with data, fit to the busiest region (no need to wait for click)
  useEffect(() => {
    const map = mapRef.current;
    if (!map || didInitialFit.current) return;
    const stats = Object.values(regions);
    if (stats.length === 0) return;
    const busiest = stats
      .filter((s) => s.messageCount > 0)
      .sort((a, b) => b.messageCount - a.messageCount)[0];
    if (busiest && useStore.getState().selectedRegion === "all") {
      // Cinematic zoom-in to the busiest region, but leave the dropdown on
      // "all regions" — don't auto-select.
      map.flyTo([busiest.lat, busiest.lon], REGION_ZOOM, FLY_OPTS_INITIAL);
    }
    didInitialFit.current = true;
  }, [regions, selectRegion]);

  return (
    <div className="relative w-full h-full">
      <div ref={containerRef} className="absolute inset-0" />
      <style>{`
        .ngo-tip {
          background: #fbfaf6;
          border: 1px solid #ddd5c1;
          color: #221f18;
          box-shadow: 0 2px 8px rgba(34, 31, 24, 0.08);
          padding: 6px 8px;
          border-radius: 6px;
        }
        .leaflet-tooltip-top.ngo-tip:before { border-top-color: #ddd5c1; }
      `}</style>
    </div>
  );
}
