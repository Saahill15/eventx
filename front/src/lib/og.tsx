import { ImageResponse } from "next/og";

export const ogSize = { width: 1200, height: 630 };

/** Branded share card used for link previews (WhatsApp, Instagram, Google). */
export function ogCard({ eyebrow, title, line1, line2 }: { eyebrow: string; title: string; line1?: string; line2?: string }) {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", padding: 72, background: "linear-gradient(135deg,#eeeef5 0%,#ffffff 55%,#e3e6fd 100%)", color: "#1b1a3a" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 22, height: 22, background: "#1530f0", borderRadius: 6, transform: "rotate(45deg)" }} />
          <div style={{ fontSize: 34, fontWeight: 800, letterSpacing: -1 }}>hiveout</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 28, fontWeight: 700, color: "#2330c9", textTransform: "uppercase", letterSpacing: 4 }}>{eyebrow}</div>
          <div style={{ fontSize: title.length > 40 ? 64 : 84, fontWeight: 900, lineHeight: 1.05, letterSpacing: -2, marginTop: 16, display: "flex" }}>{title}</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", fontSize: 32, color: "#555", gap: 8 }}>
          {line1 && <div style={{ display: "flex" }}>{line1}</div>}
          {line2 && <div style={{ display: "flex" }}>{line2}</div>}
        </div>
      </div>
    ),
    { ...ogSize },
  );
}
