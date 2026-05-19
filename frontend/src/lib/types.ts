// ============================================
// Auth
// ============================================

export interface TokenResponse {
  access_token: string;
  expires_at: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
}

export interface RegisterResponse {
  status: string;
  id: number;
  email: string;
  token: TokenResponse;
}

export interface LoginResponse {
  access_token: string;
  expires_at: string;
}

export interface SessionResponse {
  status: string;
  session_id: string;
  name: string;
  token: TokenResponse;
}

export interface SessionListItem {
  status: string;
  session_id: string;
  name: string;
  token: TokenResponse;
}

// ============================================
// Chat
// ============================================

export interface Message {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface BuilderAction {
  action: "advance" | "modify" | "back";
  selected_ids?: string[];
  day_groups?: DayGroup[];
  target_phase?: BuilderLayer;
}

export interface ChatRequest {
  messages: Message[];
  builder_action?: BuilderAction;
}

export interface Question {
  id: string;
  text: string;
  options: string[];
  allow_multiple: boolean;
}

export type BuilderLayer = "select_pois" | "group_days" | "arrange" | "confirm";
export type BuilderPhase = "gathering" | BuilderLayer;

export interface BuilderResponse {
  layer: BuilderLayer;
  data: SelectPOIsPayload | GroupDaysPayload | ArrangePayload | null;
}

export interface ChatResponse {
  status: string;
  messages: Message[];
  questions: Question[];
  builder: BuilderResponse | null;
}

// ============================================
// Session Detail (GET /chat/sessions/{id})
// ============================================

export interface HistoryMessage extends Message {
  questions?: Question[];
  builder?: BuilderResponse;
}

export interface SessionDetail {
  session_id: string;
  name: string;
  phase: BuilderPhase | null;
  messages: HistoryMessage[];
}

// ============================================
// SSE Events
// ============================================

export interface SSEGatheringEvent {
  type: "gathering";
  content: string;
  questions: Question[];
}

export interface SSEBuilderEvent {
  type: "builder";
  content: string;
  layer: BuilderLayer;
  data: SelectPOIsPayload | GroupDaysPayload | ArrangePayload | null;
}

export interface SSEAnswerEvent {
  type: "answer";
  content: string;
}

export interface SSEErrorEvent {
  type: "error";
  message: string;
}

export type SSEEvent = SSEGatheringEvent | SSEBuilderEvent | SSEAnswerEvent | SSEErrorEvent;

// ============================================
// Builder: Select POIs
// ============================================

export type POICategory = "attraction" | "restaurant" | "hotel" | "shopping" | "activity";

export interface POIMeta {
  rating: number | null;
  price: string;
  duration: string;
  distance: string;
}

export interface POIOption {
  id: string;
  name: string;
  category: POICategory;
  brief: string;
  reason: string;
  meta: POIMeta;
}

export interface SelectPOIsPayload {
  recommended: POIOption[];
  alternatives: POIOption[];
}

// ============================================
// Builder: Group Days
// ============================================

export interface DayGroup {
  day: number;
  theme: string;
  reason: string;
  items: string[];
}

export interface GroupDaysPayload {
  days: DayGroup[];
  suggestion: string;
}

// ============================================
// Builder: Arrange
// ============================================

export interface ScheduledActivity {
  time: string;
  poi_id: string;
  name: string;
  transport_to_next: string;
}

export interface DaySchedule {
  day: number;
  theme: string;
  activities: ScheduledActivity[];
}

export interface ArrangePayload {
  days: DaySchedule[];
  tips: string[];
  budget_estimate: string;
}

// ============================================
// Trip
// ============================================

export type TimeSlot = "morning" | "lunch" | "afternoon" | "dinner" | "evening";
export type ActivityCategory = "attraction" | "restaurant" | "hotel" | "shopping" | "transport" | "activity";
export type TripStatus = "draft" | "confirmed" | "completed";

export interface Activity {
  time_slot: TimeSlot;
  name: string;
  category: ActivityCategory;
  description: string;
  duration_minutes: number;
  location: string | null;
  tips: string | null;
}

export interface DayPlan {
  day: number;
  theme: string;
  activities: Activity[];
  transport_tips: string | null;
}

export interface Itinerary {
  destination: string;
  total_days: number;
  days: DayPlan[];
  tips: string[];
  budget_estimate: string | null;
}

export interface TripResponse {
  status: TripStatus;
  id: string;
  user_id: number;
  session_id: string | null;
  title: string;
  destination: string;
  total_days: number;
  itinerary: Itinerary;
  created_at: string;
  updated_at: string;
}

export interface TripListResponse {
  status: string;
  trips: TripResponse[];
  total: number;
}
