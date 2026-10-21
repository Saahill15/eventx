import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Inter } from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import { SITE_URL } from "@/lib/api";
import { MotionProvider } from "@/components/motion";
import { TopBar } from "@/components/shell/TopBar";
import { Dock } from "@/components/shell/Dock";
import { Footer } from "@/components/shell/Footer";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const bricolage = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-bricolage", display: "swap", weight: ["500", "600", "700", "800"] });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "HiveOut: every college fest in one place", template: "%s · HiveOut" },
  description: "Discover college fests, register for events in seconds and walk in with a QR pass.",
  applicationName: "HiveOut",
  icons: { icon: [{ url: "/favicon-32.png", sizes: "32x32" }, { url: "/favicon.ico" }], apple: "/apple-touch-icon.png" },
  openGraph: { siteName: "HiveOut", type: "website", locale: "en_IN" },
  twitter: { card: "summary_large_image" },
};
export const viewport: Viewport = { themeColor: "#ffffff", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${bricolage.variable}`}>
      <body className="min-h-screen pb-24 md:pb-0">
        <MotionProvider>
          <AuthProvider>
            <TopBar />
            <main>{children}</main>
            <Footer />
            <Dock />
          </AuthProvider>
        </MotionProvider>
      </body>
    </html>
  );
}
