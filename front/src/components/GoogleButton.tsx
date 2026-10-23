"use client";

import Script from "next/script";
import { useEffect, useRef, useState } from "react";

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";

interface GoogleId {
  initialize: (o: { client_id: string; callback: (r: { credential: string }) => void; ux_mode?: string }) => void;
  renderButton: (el: HTMLElement, o: Record<string, unknown>) => void;
}
const gis = () => (window as unknown as { google?: { accounts?: { id?: GoogleId } } }).google?.accounts?.id;

/**
 * "Continue with Google". Needs NEXT_PUBLIC_GOOGLE_CLIENT_ID (and GOOGLE_CLIENT_ID on the API). Until then it is shown
 * switched off during development, and not at all on the live site.
 */
export function GoogleButton({ onCredential, label = "continue_with" }: { onCredential: (credential: string) => void; label?: "signin_with" | "signup_with" | "continue_with" }) {
  const box = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const handler = useRef(onCredential);
  handler.current = onCredential;

  useEffect(() => {
    const id = gis();
    if (!CLIENT_ID || !ready || !id || !box.current) return;
    id.initialize({ client_id: CLIENT_ID, callback: (r) => handler.current(r.credential) });
    id.renderButton(box.current, { theme: "outline", size: "large", shape: "pill", text: label, width: box.current.offsetWidth || 320 });
  }, [ready, label]);

  if (!CLIENT_ID) {
    if (process.env.NODE_ENV !== "development") return null;
    return (
      <div>
        <button type="button" disabled className="flex h-12 w-full items-center justify-center gap-3 rounded-full border border-black/10 bg-white text-sm font-semibold text-mute opacity-60">
          <GoogleMark /> Continue with Google
        </button>
        <p className="mt-1.5 text-center text-xs text-mute">Development only: set NEXT_PUBLIC_GOOGLE_CLIENT_ID to switch this on.</p>
      </div>
    );
  }
  return (
    <>
      <Script src="https://accounts.google.com/gsi/client" strategy="afterInteractive" onReady={() => setReady(true)} />
      <div ref={box} className="flex min-h-12 w-full justify-center" />
    </>
  );
}

function GoogleMark() {
  return (
    <svg viewBox="0 0 48 48" className="h-5 w-5" aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5z" />
    </svg>
  );
}
