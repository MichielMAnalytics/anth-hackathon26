import { IncidentMap } from "../components/map/IncidentMap";
import { RegionPanel } from "../components/map/RegionPanel";

export function MapView() {
  return (
    <div className="h-full grid grid-cols-[1fr_380px] min-h-0">
      <div className="min-h-0 border-r border-paper-200">
        <IncidentMap />
      </div>
      <aside className="min-h-0 overflow-y-auto bg-paper-50">
        <RegionPanel />
      </aside>
    </div>
  );
}
