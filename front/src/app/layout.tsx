import type { Metadata, Viewport } from "next";
import { Archivo, Inter } from "next/font/google";
import { AuthProvider } from "@/lib/auth";
import { MotionProvider } from "@/components/motion";
import { SITE_URL } from "@/lib/api";
import { Footer } from "@/components/Footer";
import { Navbar } from "@/components/Navbar";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const archivo = Archivo({ subsets: ["latin"], variable: "--font-archivo", display: "swap", weight: ["600", "700", "800", "900"] });

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "HiveOut: every college fest in one place", template: "%s · HiveOut" },
  description: "Discover college fests, register for events in seconds and walk in with a QR pass.",
  applicationName: "HiveOut",
  icons: { icon: [{ url: "/favicon-32.png", sizes: "32x32" }, { url: "/favicon.ico" }], apple: "/apple-touch-icon.png" },
  openGraph: { siteName: "HiveOut", type: "website", locale: "en_IN" },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = { themeColor: "#faf9f7", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${archivo.variable}`}>
      <body className="min-h-screen">
        <MotionProvider>
          <AuthProvider>
            <Navbar />
            <main className="pt-20 sm:pt-24">{children}</main>
            <Footer />
          </AuthProvider>
        </MotionProvider>
      </body>
    </html>
  );
}
