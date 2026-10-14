import { Product } from "@/types";

export type MessageRole = "user" | "assistant" | "system";

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

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: string; // ISO or HH:mm
  recommendedProducts?: ChatProductItem[];
  safetyAlert?: ChatSafetyAlert;
  quickReplies?: string[];
  isError?: boolean;
}

export interface ChatRequest {
  message: string;
  conversationHistory?: Array<{
    role: "user" | "assistant";
    content: string;
  }>;
  sessionId?: string;
}

export interface ChatResponse {
  reply: string;
  recommendedProducts?: ChatProductItem[];
  safetyAlert?: ChatSafetyAlert;
  quickReplies?: string[];
  providerUsed: string;
  modelUsed?: string;
}
