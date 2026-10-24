"use client";

import { createContext, useContext } from "react";
import type { Bot } from "@/lib/types";

export const BotContext = createContext<{ bot: Bot; setBot: (b: Bot) => void } | null>(null);

export function useBot() {
  const ctx = useContext(BotContext);
  if (!ctx) throw new Error("useBot must be used inside the bot layout");
  return ctx;
}
