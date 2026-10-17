import { Product } from "@/types";

export type MessageRole = "user" | "assistant" | "system";

/**
 * 10 Intent Router chuẩn theo quy chuẩn y tế H4CARE (Phần III)
 */
export type StandardIntent =
  | "GREETING"              // 1. Chào hỏi
  | "GENERAL_CHAT"          // 2. Hội thoại thông thường / chitchat / cảm ơn / giới thiệu
  | "HEALTH_SYMPTOM"        // 3. Tư vấn triệu chứng sức khỏe
  | "HEALTH_EDUCATION"     // 4. Kiến thức sức khỏe, phòng bệnh, dinh dưỡng
  | "DRUG_INFORMATION"      // 5. Thông tin dược lý hoạt chất, tác dụng phụ, tương tác
  | "PRODUCT_SEARCH"        // 6. Tìm sản phẩm, giá, tồn kho trong hệ thống H4CARE
  | "PRESCRIPTION_SUPPORT"  // 7. Hỗ trợ mua thuốc kê đơn (Rx)
  | "ORDER_SUPPORT"         // 8. Tra cứu đơn hàng, chính sách đổi trả, vận chuyển
  | "HUMAN_SUPPORT"         // 9. Yêu cầu kết nối Dược sĩ / nhân viên thật
  | "EMERGENCY";            // 10. Dấu hiệu nguy hiểm khẩn cấp (Red Flags / Cấp cứu 115)

export interface ChatProductItem {
  id: string;
  name: string;
  slug: string;
  brand: string;
  categoryName: string;
  price: number;
  salePrice?: number | null;
  image: string;
  activeIngredient: string;
  dosageForm: string;
  stock: number;
  isPrescription: boolean;
  shortDescription: string;
}

export interface ChatSafetyAlert {
  level: "emergency" | "warning" | "info";
  title: string;
  message: string;
  actionRequired?: string;
  emergencyNumber?: string;
}

export interface ChatAttachment {
  id: string;
  fileName: string;
  name?: string;
  storedFileName: string;
  fileSize: number;
  size?: number;
  mimeType: string;
  mime_type?: string;
  type?: string;
  url: string;
  base64Data?: string;
  data_base64?: string;
  uploadedAt: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string; // ISO or HH:mm
  recommendedProducts?: ChatProductItem[];
  safetyAlert?: ChatSafetyAlert;
  quickReplies?: string[];
  isError?: boolean;
  apiStatus?: "real_llm_success" | "quota_exceeded" | "api_error" | "offline_expert_system";
  modelUsed?: string;
  latencyMs?: number;
  attachments?: ChatAttachment[];
}

export interface SymptomContext {
  primarySymptom?: string; // e.g. "đau bụng dưới", "đau đầu", "sốt", "ho"
  duration?: string;       // e.g. "từ hôm qua", "2 ngày"
  location?: string;       // e.g. "bên phải", "bên trái", "giữa bụng"
  severity?: string;       // e.g. "âm ỉ", "dữ dội", "quặn từng cơn"
  accompanying?: string[]; // e.g. ["sốt", "nôn", "ngất", "chóng mặt"]
  patientType?: string;    // e.g. "người lớn", "trẻ em"
  step: number;            // 1, 2, 3, 4
  hasRedFlag?: boolean;
  redFlagReason?: string;
}

export interface ExtractedMemory {
  userName?: string;
  age?: string;
  gender?: string;
  symptoms?: string[];
  symptomDuration?: string;
  symptomSeverity?: string;
  symptomLocation?: string;
  symptomEscalated?: boolean;
  userMood?: string;
  firstDiscussedProduct?: string;
  currentMedicines?: string[];
  requestedRealPharmacist?: boolean;
  lastDiscussedProduct?: string;
  lastTopic?: string;
  unresolvedQuestion?: string;
  contextSummary?: string;
  lastAttachedImage?: {
    fileName: string;
    url: string;
    description?: string;
    activeDrug?: string;
  };
  correctedFacts?: Record<string, { previous: any; current: any; timestamp: string }>;
}

export interface ChatConversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ChatMessage[];
  extractedMemory: ExtractedMemory;
  userId?: string | number | null;
  sessionId: string;
  isPinned?: boolean;
}

export interface ConversationContext {
  lastIntent?: StandardIntent;
  activeDrug?: string;          // e.g. "Paracetamol", "Ibuprofen", "Vitamin C"
  activeProductSlug?: string;
  symptomContext?: SymptomContext;
  extractedMemory?: ExtractedMemory;
  contextSummary?: string;
}

export interface ChatRequest {
  message: string;
  conversationHistory?: Array<{
    role: "user" | "assistant";
    content: string;
  }>;
  sessionId?: string;
  conversationId?: string;
  extractedMemory?: ExtractedMemory;
  attachments?: ChatAttachment[];
  contextProduct?: {
    id: string;
    name: string;
    slug: string;
    brand?: string;
    activeIngredient?: string;
    price?: number;
    isPrescription?: boolean;
  };
  currentUser?: {
    fullName?: string;
    phone?: string;
    email?: string;
    isAuthenticated?: boolean;
  };
}

export interface ChatResponse {
  reply: string;
  recommendedProducts?: ChatProductItem[];
  safetyAlert?: ChatSafetyAlert;
  quickReplies?: string[];
  providerUsed: string;
  modelUsed?: string;
  intentDetected?: StandardIntent;
  sourceAttribution?: string;
  isHumanSupport?: boolean;
  sessionId?: string;
  extractedMemory?: ExtractedMemory;
  handoffRequested?: boolean;
  contextSummary?: string;
  apiStatus?: "real_llm_success" | "quota_exceeded" | "api_error" | "offline_expert_system";
  apiErrorDetail?: string;
  latencyMs?: number;
}
