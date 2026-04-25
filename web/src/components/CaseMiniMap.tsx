import { useEffect, useRef } from "react";
import L from "leaflet";
import type { Incident } from "../lib/types";

const SEV_COLOR: Record<string, string> = {
  critical: "#c11f1f",
  high: "#b07636",
  medium: "#a17e2e",
  low: "#3f7d4f",
};

export function CaseMiniMap({ incident }: { incident: Incident }) {
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<L.Map | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    if (typeof incident.lat !== "number" || typeof incident.lon !== "number")
      return;

    if (!mapRef.current) {
      mapRef.current = L.map(ref.current, {
        zoomControl: false,
        attributionControl: false,
        dragging: false,
        scrollWheelZoom: false,
        doubleClickZoom: false,
      });
      L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        { subdomains: "abcd" },
      ).addTo(mapRef.current);
    }
    const m = mapRef.current!;
    m.setView([incident.lat, incident.lon], 9);
    m.eachLayer((layer) => {
      if ((layer as L.CircleMarker).getLatLng) {
        m.removeLayer(layer);
      }
    });
    L.circleMarker([incident.lat, incident.lon], {
      radius: 10,
      color: SEV_COLOR[incident.severity] ?? "#c11f1f",
      fillColor: SEV_COLOR[incident.severity] ?? "#c11f1f",
      fillOpacity: 0.32,
      weight: 2,
    }).addTo(m);

    return () => {
      // keep map alive across re-renders for the same component
    };
  }, [incident.id, incident.lat, incident.lon, incident.severity]);

  useEffect(() => {
    return () => {
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  if (typeof incident.lat !== "number") {
    return (
      <div className="rounded-md border border-surface-300 bg-surface-100 p-4 text-meta text-ink-500">
        No location on file for this case.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-surface-300 overflow-hidden">
      <div ref={ref} className="h-32 w-full" />
    </div>
  );
}
