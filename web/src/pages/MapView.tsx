import { IncidentMap } from "../components/map/IncidentMap";
import { RegionPanel } from "../components/map/RegionPanel";

export function MapView() {
  return (
    <div className="h-full flex flex-col md:grid md:grid-cols-[1fr_380px] min-h-0">
      <div className="h-[55vh] md:h-auto min-h-0 md:border-r border-surface-300">
        <IncidentMap />
      </div>
      <aside className="flex-1 min-h-0 overflow-y-auto bg-white border-t md:border-t-0 border-surface-300">
        <RegionPanel />
      </aside>
    </div>
  );
}
