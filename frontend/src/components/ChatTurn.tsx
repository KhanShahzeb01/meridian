"use client";

import { ChatMessage } from "@/lib/storage";
import ChatBox from "./ChatBox";

interface ChatTurnProps {
  query?: ChatMessage;
  assistant?: ChatMessage;
  system?: ChatMessage;
}

function PlainText({ text }: { text: string }) {
  return (
    <div className="whitespace-pre-wrap break-words text-sm leading-[1.55] text-[#cbd5e1]">
      {text}
    </div>
  );
}

export default function ChatTurn({ query, assistant, system }: ChatTurnProps) {
  if (system) {
    return (
      <div className="chat-turn">
        <ChatBox variant="system" markdown>
          {system.content}
        </ChatBox>
      </div>
    );
  }

  const sections = assistant?.sections;
  const hasStructured =
    sections &&
    (sections.planning || sections.thinking || sections.response || sections.extra);

  return (
    <div className="chat-turn space-y-2">
      {query && (
        <ChatBox variant="query" mono>
          <span className="text-[#93c5fd]">{query.content}</span>
        </ChatBox>
      )}

      {assistant && hasStructured ? (
        <>
          {sections?.planning && (
            <ChatBox variant="planning" mono>
              <PlainText text={sections.planning} />
            </ChatBox>
          )}
          {sections?.thinking && (
            <ChatBox variant="thinking" mono>
              <PlainText text={sections.thinking} />
            </ChatBox>
          )}
          {sections?.response && (
            <ChatBox variant="response" markdown>
              {sections.response}
            </ChatBox>
          )}
          {sections?.panels?.map((panel) => (
            <ChatBox key={`${panel.title}-${panel.content.slice(0, 24)}`} variant="output" title={panel.title} markdown>
              {panel.content}
            </ChatBox>
          ))}
          {sections?.extra && !sections?.response && (
            <ChatBox variant="output" markdown>
              {sections.extra}
            </ChatBox>
          )}
        </>
      ) : assistant ? (
        <ChatBox
          variant={assistant.type === "error" ? "output" : "response"}
          title={assistant.type === "error" ? "Error" : "Response"}
          markdown
        >
          {assistant.content}
        </ChatBox>
      ) : null}

      {assistant?.persona && (
        <div className="px-1 font-mono text-[10px] uppercase tracking-wider text-[var(--color-accent)]">
          via {assistant.persona}
        </div>
      )}
    </div>
  );
}
