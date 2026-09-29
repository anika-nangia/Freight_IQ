import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  EAST_COAST_PORTS,
  fetchPortMap,
  mapFastAPIPortNameToFrontendPort,
  type Port,
  type CargoInput,
} from "../services/api";
import FreightForecastModule from "../components/modules/FreightForecastModule";
import MarketEntryModule from "../components/modules/MarketEntryModule";
import VesselOptimizerModule from "../components/modules/VesselOptimizerModule";
import IdleAnalysisModule from "../components/modules/IdleAnalysisModule";
import RiskMonitorModule from "../components/modules/RiskMonitorModule";

const TABS = [
  { id: "forecast", label: "Freight Forecast" },
  { id: "market", label: "Market Entry" },
  { id: "vessel", label: "Vessel Optimizer" },
  { id: "idle", label: "Idle Analysis" },
  { id: "risk", label: "Risk Monitor" },
];

export default function PortIntelligence() {
  const { portId } = useParams<{ portId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState("forecast");
  const [backendPort, setBackendPort] = useState<Port | undefined>(undefined);

  const port: Port | undefined = EAST_COAST_PORTS.find((p) => p.id === portId);
  const rawCargo = sessionStorage.getItem("freightiq_cargo");
  const cargo: CargoInput = rawCargo
    ? JSON.parse(rawCargo)
    : { cargoType: "Iron Ore", quantity: 50000, origin: "Paradip", destination: "Vizag", vesselPreference: "Supramax", contractDuration: "Spot", laycanDate: "2025-09-18", constraints: "" };

  useEffect(() => {
    window.scrollTo(0, 0);

    fetchPortMap()
      .then((data) => {
        const destinationNodes = data.nodes.filter(
          (node: { role: string }) => node.role === "destination"
        );

        const matchingNode = destinationNodes.find(
          (node: { name: string }) =>
            mapFastAPIPortNameToFrontendPort(node.name)?.id === portId
        );

        if (matchingNode) {
          setBackendPort(mapFastAPIPortNameToFrontendPort(matchingNode.name));
        }
      })
      .catch((error) => {
        console.error("FastAPI port map error:", error);
      });
  }, [portId]);

  if (!port) {
    return (
      <div className="p-8 text-center" style={{ color: "#5a7d96" }}>
        Port not found.{" "}
        <button onClick={() => navigate("/dashboard")} style={{ color: "#0ecad4" }}>Back to dashboard</button>
      </div>
    );
  }

  return (
    <div className="p-6 animate-fade-in" style={{ fontFamily: "Inter, sans-serif" }}>
      {/* Back + Header */}
      <div className="mb-6">
        <button
          onClick={() => navigate("/dashboard")}
          className="flex items-center gap-2 text-xs mb-4 transition-colors"
          style={{ color: "#5a7d96" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "#0ecad4")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "#5a7d96")}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="w-4 h-4">
            <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
          </svg>
          Back to Dashboard
        </button>

        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <div className="w-2 h-2 rounded-full" style={{ background: port.status === "operational" ? "#10b981" : "#f59e0b" }} />
              <h1 className="text-2xl font-bold" style={{ fontFamily: "Outfit, sans-serif", color: "#e8f1f8" }}>
                {port.name} Port Intelligence
                {backendPort && (
                  <span
                    className="text-xs ml-2"
                    style={{ color: "#10b981" }}
                  >
                    · Backend connected
                  </span>
                )}
              </h1>
              <span className="text-xs px-2 py-0.5 rounded mono" style={{ background: "rgba(14,202,212,0.08)", color: "#5a7d96" }}>
                {port.state}
              </span>
            </div>
          </div>
          <div className="text-xs px-4 py-2 rounded-lg" style={{ background: "rgba(14,202,212,0.06)", border: "1px solid rgba(14,202,212,0.12)", color: "#5a7d96" }}>
            <span style={{ color: "#0ecad4" }}>AI Analysis Active</span> · Updated just now
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 mb-6 p-1 rounded-xl overflow-x-auto" style={{ background: "rgba(14,202,212,0.04)", border: "1px solid rgba(14,202,212,0.08)" }}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className="px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap"
            style={{
              background: activeTab === tab.id ? "rgba(14,202,212,0.15)" : "transparent",
              color: activeTab === tab.id ? "#0ecad4" : "#5a7d96",
              fontFamily: "Inter, sans-serif",
              border: activeTab === tab.id ? "1px solid rgba(14,202,212,0.25)" : "1px solid transparent",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Module content */}
      <div className="animate-fade-in">
        {activeTab === "forecast" && <FreightForecastModule port={port} cargo={cargo} />}
        {activeTab === "market" && <MarketEntryModule port={port} cargo={cargo} />}
        {activeTab === "vessel" && <VesselOptimizerModule port={port} cargo={cargo} />}
        {activeTab === "idle" && <IdleAnalysisModule port={port} cargo={cargo} />}
        {activeTab === "risk" && <RiskMonitorModule port={port} cargo={cargo} />}
      </div>
    </div>
  );
}

