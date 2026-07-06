"use client";

import { useState } from "react";
import dynamic from "next/dynamic";

const DynamicMap = dynamic(() => import("@/components/Map"), {
  ssr: false,
  loading: () => <div style={{display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: '#38bdf8'}}>Loading Chart...</div>
});

export default function Home() {
  const [input, setInput] = useState("");
  const [briefing, setBriefing] = useState("");
  const [routeData, setRouteData] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    setLoading(true);
    setBriefing("");
    setRouteData(null);
    setBriefing("Processing request... Gathering weather data... Planning route...");
    
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8001";
      const res = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: input })
      });
      if (!res.ok) throw new Error("Network response was not ok");
      const data = await res.json();
      
      let textResponse = data.response;
      let parsed;
      if (typeof textResponse === 'string') {
        const jsonMatch = textResponse.match(/```(?:json)?\n([\s\S]*?)\n```/);
        if (jsonMatch) {
          textResponse = jsonMatch[1];
        }
        try {
          parsed = JSON.parse(textResponse);
        } catch (e) {
          parsed = { briefing_text: textResponse };
        }
      } else {
        parsed = textResponse;
      }
      setBriefing(parsed.briefing_text || "Done.");
      
      // route_data comes from the backend directly, avoiding LLM truncation
      if (data.route_data) {
        setRouteData(data.route_data);
      } else if (parsed.route) {
        setRouteData(parsed.route);
      } else {
        setRouteData(null);
      }
    } catch (error) {
      console.error(error);
      setBriefing("An error occurred while communicating with the agent.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <header className="glass-header">
        <div>
          <h1 className="title-glow">Sailing Maps</h1>
          <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "2px" }}>
            Richmond Navigator
          </div>
        </div>
        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          <div className="status-indicator">
            <span className="pulse-dot"></span>
            SYSTEM ONLINE
          </div>
        </div>
      </header>
      
      <main className="main-container">
        <aside className="sidebar glass-panel">
          <h2>Concierge Agent</h2>
          
          <div className="chat-pane">
            <div className="chat-message bot">
              Hello! I can help you plan a sailing trip in San Francisco Bay. Tell me where you want to go and when.
            </div>
            {briefing && (
                <div className="chat-message bot">
                    {briefing}
                </div>
            )}
            {routeData && routeData.status === "infeasible" && (
                <div className="chat-message error">
                    Route infeasible: {routeData.reason}
                </div>
            )}
          </div>
          
          <form onSubmit={handleSubmit} style={{display: 'flex', flexDirection: 'column', gap: '8px', marginTop: 'auto'}}>
            <textarea 
                className="input-field" 
                rows={3}
                placeholder="E.g., 3 hour sail from Berkeley tomorrow at 1pm, we draw 1.8m, want to see Alcatraz"
                value={input}
                onChange={e => setInput(e.target.value)}
                disabled={loading}
            />
            <button className="btn" type="submit" disabled={loading}>
              {loading ? "Planning..." : "Send Request"}
            </button>
          </form>

          {routeData && routeData.status === "ok" && (
            <div className="route-info">
              <div className="stat-row">
                <span>Return ETA</span>
                <span className="stat-val">{new Date(routeData.return_eta).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
              </div>
              <div className="stat-row">
                <span>Sunset Margin</span>
                <span className="stat-val">{routeData.sunset_margin_min} min</span>
              </div>
            </div>
          )}
        </aside>
        
        <section className="map-container dashboard-panel">
          <div className="dashboard-overlay top-left">NOAA DEM GRID v1 // 200m RES</div>
          <div className="dashboard-overlay bottom-right">WARNING: NOT TO BE USED FOR NAVIGATION</div>
          <div className="map-wrapper">
            <DynamicMap 
              coordinates={routeData?.coordinates} 
              legs={routeData?.legs} 
            />
          </div>
        </section>
      </main>
    </>
  );
}
