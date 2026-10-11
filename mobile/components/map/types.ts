import { PlaceSummary } from "../../lib/api/places";

export interface MapRegion {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
}

export interface PlacesMapProps {
  initialRegion: MapRegion;
  places: PlaceSummary[];
  colors: Record<string, string>;
  userLocation: { lat: number; lng: number } | null;
  /** Bumped to ask the map to fly to the user's location. */
  recenterKey: number;
  onRegionChange: (region: MapRegion) => void;
  onSelect: (place: PlaceSummary | null) => void;
}
