import { useEffect, useState } from "react";

export type Route = "dashboard" | "cases" | "map";

const PATH_TO_ROUTE: Record<string, Route> = {
  "/": "dashboard",
  "/cases": "cases",
  "/map": "map",
};

const ROUTE_TO_PATH: Record<Route, string> = {
  dashboard: "/",
  cases: "/cases",
  map: "/map",
};

const NAV_EVENT = "safethread:navigate";

function currentRoute(): Route {
  return PATH_TO_ROUTE[window.location.pathname] ?? "dashboard";
}

export function navigate(route: Route, opts?: { replace?: boolean }) {
  const path = ROUTE_TO_PATH[route];
  if (window.location.pathname === path) return;
  if (opts?.replace) {
    window.history.replaceState(null, "", path);
  } else {
    window.history.pushState(null, "", path);
  }
  window.dispatchEvent(new Event(NAV_EVENT));
}

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(currentRoute);
  useEffect(() => {
    const update = () => setRoute(currentRoute());
    window.addEventListener("popstate", update);
    window.addEventListener(NAV_EVENT, update);
    return () => {
      window.removeEventListener("popstate", update);
      window.removeEventListener(NAV_EVENT, update);
    };
  }, []);
  return route;
}
