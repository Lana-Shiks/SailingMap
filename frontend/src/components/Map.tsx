"use client";

import { MapContainer, TileLayer, WMSTileLayer, Marker, Popup, Polyline, LayerGroup } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import L from "leaflet";

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl: "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

const warningIcon = L.divIcon({
  html: `<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffcc00" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 0 6px #ffcc00);"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
  className: "",
  iconSize: [24, 24],
  iconAnchor: [12, 12],
});

interface MapProps {
  coordinates?: [number, number][];
  legs?: any[];
}

export default function Map({ coordinates, legs }: MapProps) {
  const center: [number, number] = [37.8200, -122.3600];

  return (
    <MapContainer 
      center={center} 
      zoom={11} 
      style={{ height: "100%", width: "100%", borderRadius: "16px" }}
    >
      <WMSTileLayer
        attribution='&copy; <a href="https://nauticalcharts.noaa.gov/">NOAA</a> | NOT TO BE USED FOR NAVIGATION'
        url="https://gis.charttools.noaa.gov/arcgis/rest/services/MCS/NOAAChartDisplay/MapServer/exts/MaritimeChartService/WMSServer"
        layers="0,1,2,3"
        format="image/png"
        transparent={true}
        className="map-tiles-high-tech"
      />
      
      {coordinates && coordinates.length > 0 && (
        <Marker position={coordinates[0]}>
          <Popup>Start</Popup>
        </Marker>
      )}

      {coordinates && legs && legs.map((leg, i) => {
        const seg = coordinates.slice(leg.from_idx, leg.to_idx + 1);
        
        let color = "#00f3ff"; // default reaching
        let dashArray = undefined;
        
        if (leg.flags && leg.flags.includes("tacking_required")) {
          color = "#ff0055"; // dashed red
          dashArray = "10, 10";
        } else if (leg.point_of_sail === "downwind") {
          color = "#00ff88"; // green
        }

        const isLaneCrossing = leg.flags && leg.flags.includes("lane_crossing");
        const midPt = seg[Math.floor(seg.length / 2)];

        return (
          <LayerGroup key={`leg-${i}`}>
            <Polyline 
              positions={seg} 
              color={color} 
              weight={4} 
              dashArray={dashArray} 
              opacity={0.8}
            />
            {isLaneCrossing && midPt && (
              <Marker position={midPt} icon={warningIcon}>
                <Popup>Warning: Shipping Lane Crossing</Popup>
              </Marker>
            )}
          </LayerGroup>
        );
      })}
    </MapContainer>
  );
}
