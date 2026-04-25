import { useEffect, useMemo, useRef } from "react";
import L from "leaflet";
import "leaflet.heat";
import { useStore } from "../../lib/store";
import type { Incident, Severity } from "../../lib/types";

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

  const incidents = useStore((s) => s.incidents);
  const regions = useStore((s) => s.regions);
  const selectRegion = useStore((s) => s.selectRegion);

  // initialize once
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = L.map(containerRef.current, {
      zoomControl: true,
      attributionControl: false,
    }).setView([30, 40], 4);

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

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // points for heatmap (one per incident, weighted by message count)
  const heatPoints = useMemo<[number, number, number][]>(() => {
    return Object.values(incidents)
      .filter(
        (i): i is Incident & { lat: number; lon: number } =>
          typeof i.lat === "number" && typeof i.lon === "number",
      )
      .map((i) => [i.lat, i.lon, Math.min(1, 0.2 + i.messageCount * 0.15)]);
  }, [incidents]);

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
          map.flyTo([inc.lat as number, inc.lon as number], 6, { duration: 0.6 });
        });
      group.addLayer(c);
    });

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
          map.flyTo([rs.lat, rs.lon], 6, { duration: 0.6 });
        });
      group.addLayer(c);
    });
  }, [heatPoints, incidents, regions, selectRegion]);

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
