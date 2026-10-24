"use client";

import ChatPanel from "@/components/ChatPanel";
import { useBot } from "../BotContext";

export default function PlaygroundPage() {
  const { bot } = useBot();
  return (
    <div className="space-y-3">
      <p className="text-sm text-ink-2">
        Test your bot before embedding it. Playground questions are counted in analytics, tagged as playground.
      </p>
      <div className="h-[70vh] overflow-hidden rounded-xl border border-line">
        <ChatPanel
          endpoint={`/bots/${bot.id}/chat`}
          welcome={bot.welcome_message}
          showDiagnostics
        />
      </div>
    </div>
  );
}
