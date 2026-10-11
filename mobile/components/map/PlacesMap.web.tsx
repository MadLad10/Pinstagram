import "leaflet/dist/leaflet.css";
import type { Map as LeafletMap } from "leaflet";
import { useEffect, useRef } from "react";
import { CircleMarker, MapContainer, TileLayer, useMapEvents } from "react-leaflet";
import { PlacesMapProps } from "./types";

/** Web map: Leaflet + OpenStreetMap tiles (react-native-maps has no web support). */
function RegionEvents({ onRegionChange, onSelect }: Pick<PlacesMapProps, "onRegionChange" | "onSelect">) {
  const map = useMapEvents({
    moveend: () => {
      const b = map.getBounds();
      const c = b.getCenter();
      onRegionChange({
        latitude: c.lat,
        longitude: c.lng,
        latitudeDelta: b.getNorth() - b.getSouth(),
        longitudeDelta: b.getEast() - b.getWest(),
      });
    },
    click: () => onSelect(null),
  });
  return null;
}

export default function PlacesMap({
  initialRegion,
  places,
  colors,
  userLocation,
  recenterKey,
  onRegionChange,
  onSelect,
}: PlacesMapProps) {
  const mapRef = useRef<LeafletMap | null>(null);

  useEffect(() => {
    if (recenterKey && userLocation) mapRef.current?.flyTo([userLocation.lat, userLocation.lng], 15);
  }, [recenterKey]);

  return (
    <MapContainer
      ref={mapRef}
      center={[initialRegion.latitude, initialRegion.longitude]}
      zoom={12}
      style={{ flex: 1, height: "100%", width: "100%" }}
      zoomControl={false}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <RegionEvents onRegionChange={onRegionChange} onSelect={onSelect} />
      {userLocation && (
        <CircleMarker
          center={[userLocation.lat, userLocation.lng]}
          radius={7}
          pathOptions={{ color: "#fff", weight: 2, fillColor: "#2563EB", fillOpacity: 1 }}
        />
      )}
      {places.map((place) => (
        <CircleMarker
          key={place.id}
          center={[place.lat!, place.lng!]}
          radius={9}
          pathOptions={{ color: "#fff", weight: 2, fillColor: colors[place.category] ?? "#E91E63", fillOpacity: 1 }}
          eventHandlers={{
            click: (e) => {
              e.originalEvent.stopPropagation();
              onSelect(place);
            },
          }}
        />
      ))}
    </MapContainer>
  );
}
