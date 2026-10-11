import { useEffect, useRef } from "react";
import MapView, { Marker } from "react-native-maps";
import { PlacesMapProps } from "./types";

export default function PlacesMap({
  initialRegion,
  places,
  colors,
  userLocation,
  recenterKey,
  onRegionChange,
  onSelect,
}: PlacesMapProps) {
  const ref = useRef<MapView>(null);

  useEffect(() => {
    if (recenterKey && userLocation) {
      ref.current?.animateToRegion({
        latitude: userLocation.lat,
        longitude: userLocation.lng,
        latitudeDelta: 0.03,
        longitudeDelta: 0.03,
      });
    }
  }, [recenterKey]);

  return (
    <MapView
      ref={ref}
      style={{ flex: 1 }}
      initialRegion={initialRegion}
      onRegionChangeComplete={onRegionChange}
      showsUserLocation={!!userLocation}
      onPress={() => onSelect(null)}
    >
      {places.map((place) => (
        <Marker
          key={place.id}
          coordinate={{ latitude: place.lat!, longitude: place.lng! }}
          pinColor={colors[place.category] ?? "#E91E63"}
          onPress={(e) => {
            e.stopPropagation();
            onSelect(place);
          }}
        />
      ))}
    </MapView>
  );
}
