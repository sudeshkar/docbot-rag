export type Bot = {
  id: string;
  name: string;
  public_key: string;
  instructions: string;
  welcome_message: string;
  allowed_origins: string[];
  monthly_quota: number;
  chunking_strategy: string;
  created_at: string;
  document_count?: number;
  queries_this_month?: number;
};

export type DocumentStatus = "queued" | "processing" | "ready" | "failed";

export type Doc = {
  id: string;
  title: string;
  source_type: "file" | "url";
  source_url: string | null;
  status: DocumentStatus;
  error: string | null;
  chunk_count: number;
  created_at: string;
};

export type Source = {
  index: number;
  document_id: string;
  title: string;
  heading: string | null;
  url: string | null;
  page: number | null;
  snippet: string;
};

export type ChunkingStrategy = { name: string; description: string };

export type DailyPoint = { day: string; queries: number; answered: number };

export type Analytics = {
  days: number;
  total_queries: number;
  answer_rate: number | null;
  avg_latency_ms: number | null;
  total_tokens: number;
  daily: DailyPoint[];
  unanswered: { question: string; count: number }[];
  top_documents: { document_id: string; title: string | null; citations: number }[];
};
