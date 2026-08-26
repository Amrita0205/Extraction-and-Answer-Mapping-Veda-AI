import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VedaAI — Extraction & Answer Mapping",
  description:
    "Upload a question paper and a handwritten answer sheet, and see which question was answered, where the answer is, and what was left blank.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#eeeeee",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  // suppressHydrationWarning is one level deep — it covers attributes on
  // <html> itself and nothing inside it. Extensions and theme scripts add
  // attributes to <html> before React hydrates, which React then reports as a
  // mismatch; this silences that without hiding real mismatches in the app's
  // own components.
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        {/*
          React hoists these into <head>. Declaring them here rather than in a
          literal <head> element avoids competing with the head Next injects.

          Loaded by <link> rather than next/font so the production build never
          depends on reaching Google Fonts at compile time — a build that fails
          on a CI network hiccup the night before a deadline is not worth the
          marginal request saving.
        */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          rel="stylesheet"
          precedence="default"
          href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,500;12..96,600;12..96,700;12..96,800&display=swap"
        />
        {children}
      </body>
    </html>
  );
}
