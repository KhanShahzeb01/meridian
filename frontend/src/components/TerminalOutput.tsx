"use client";

import { useRef, useEffect, useMemo } from "react";
import { ChatMessage } from "@/lib/storage";
import ChatTurn from "./ChatTurn";
import ChatBox from "./ChatBox";

interface TerminalOutputProps {
  messages: ChatMessage[];
  isLoading: boolean;
  pendingQuery?: string;
}

interface Turn {
  query?: ChatMessage;
  assistant?: ChatMessage;
  system?: ChatMessage;
}

function groupTurns(messages: ChatMessage[]): Turn[] {
  const turns: Turn[] = [];
  let pending: Turn | null = null;

  for (const msg of messages) {
    if (msg.role === "system") {
      if (pending) {
        turns.push(pending);
        pending = null;
      }
      turns.push({ system: msg });
      continue;
    }

    if (msg.role === "user") {
      if (pending?.assistant) {
        turns.push(pending);
      }
      pending = { query: msg };
      continue;
    }

    if (msg.role === "assistant") {
      if (pending) {
        pending.assistant = msg;
        turns.push(pending);
        pending = null;
      } else {
        turns.push({ assistant: msg });
      }
    }
  }

  if (pending) {
    turns.push(pending);
  }

  return turns;
}

function loadingLabel(query: string): string {
  const cmd = query.trim().split(/\s+/)[0]?.toLowerCase();
  const labels: Record<string, string> = {
    "/memo": "Drafting fast memo (quote + single LLM pass)…",
    "/research": "Running deep research with tools…",
    "/consensus": "Running expert consensus panel…",
    "/screen": "Running multi-agent screener…",
    "/dcf": "Computing DCF valuation…",
    "/ask": "Consulting persona…",
    "/debate": "Running persona debate…",
  };
  return labels[cmd] || "Planning and gathering data…";
}

export default function TerminalOutput({
  messages,
  isLoading,
  pendingQuery,
}: TerminalOutputProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const turns = useMemo(() => groupTurns(messages), [messages]);

  const lastTurn = turns[turns.length - 1];
  const pendingOnLastTurn = Boolean(
    isLoading &&
      pendingQuery &&
      lastTurn?.query?.content === pendingQuery &&
      !lastTurn?.assistant
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, pendingQuery]);

  return (
    <div className="flex-1 overflow-y-auto terminal-scroll px-4 py-4 space-y-5">
      {turns.map((turn, idx) => {
        const showPlanning =
          pendingOnLastTurn && idx === turns.length - 1;
        return (
          <div
            key={turn.query?.id || turn.assistant?.id || turn.system?.id || idx}
            className="fade-in"
          >
            <ChatTurn
              query={turn.query}
              assistant={turn.assistant}
              system={turn.system}
            />
            {showPlanning && pendingQuery && (
              <div className="mt-2">
                <ChatBox variant="planning" mono>
                  <div className="flex items-center gap-2 text-[var(--color-muted)]">
                    <span className="inline-flex gap-1">
                      <span className="animate-pulse">●</span>
                      <span className="animate-pulse" style={{ animationDelay: "0.2s" }}>●</span>
                      <span className="animate-pulse" style={{ animationDelay: "0.4s" }}>●</span>
                    </span>
                    {loadingLabel(pendingQuery)}
                  </div>
                </ChatBox>
              </div>
            )}
          </div>
        );
      })}

      {isLoading && pendingQuery && !pendingOnLastTurn && (
        <div className="chat-turn space-y-2 fade-in">
          <ChatBox variant="query" mono>
            <span className="text-[#93c5fd]">{pendingQuery}</span>
          </ChatBox>
          <ChatBox variant="planning" mono>
            <div className="flex items-center gap-2 text-[var(--color-muted)]">
              <span className="inline-flex gap-1">
                <span className="animate-pulse">●</span>
                <span className="animate-pulse" style={{ animationDelay: "0.2s" }}>●</span>
                <span className="animate-pulse" style={{ animationDelay: "0.4s" }}>●</span>
              </span>
              {loadingLabel(pendingQuery)}
            </div>
          </ChatBox>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
