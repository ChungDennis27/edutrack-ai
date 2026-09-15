import ChatPanel from "@/components/common/ChatPanel";

export default function ChatBot() {
  return (
    <div className="animate-fade-in">
      <ChatPanel
        showSubjectSelector
        emptyTitle="AI 智能導師"
        emptyHint="歡迎提問任何 DSE 課題問題。數學題會提供步驟提示而非直接答案。"
        suggestions={[
          "解釋二次方程判別式的意義",
          "「克己復禮為仁」點解？",
          "How to improve my DSE essay organization?",
        ]}
        className="h-[calc(100vh-12rem)]"
      />
    </div>
  );
}
