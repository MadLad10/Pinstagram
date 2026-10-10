export interface WalkStep { type: "walk"; to: string; distance_m: number; duration_s: number }
export interface BusStep {
  type: "bus"; route_name: string; operator: string | null; from_stop: string; to_stop: string;
  num_stops: number; duration_s: number; fare: number;
}
export interface TrainStep {
  type: "train"; from_station: string; to_station: string; departure_time: string | null;
  duration_s: number; fare: number;
}
export interface RideHailProvider { name: string; cost_low: number; cost_high: number; duration_s: number }

interface Base { total_cost: number; total_duration_s: number; label: string | null }
export type DirectionsOption =
  | (Base & { mode: "bus"; steps: (WalkStep | BusStep)[] })
  | (Base & { mode: "ride_hail"; providers: RideHailProvider[]; distance_m: number })
  | (Base & { mode: "train"; steps: (WalkStep | TrainStep)[]; next_departure: string | null; fare: number })
  | (Base & { mode: "walk"; distance_m: number; recommended: boolean });

export interface Directions { distance_m: number; options: DirectionsOption[] }
