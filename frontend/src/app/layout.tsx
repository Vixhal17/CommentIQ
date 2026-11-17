import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "CommentIQ — YouTube Comment Intelligence",
  description: "Human-supervised AI comment triage with hybrid RAG grounding and risk routing",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} dark`}>
      <body className="antialiased bg-canvas text-primary font-sans min-h-screen selection:bg-accent/25 selection:text-white">
        {children}
      </body>
    </html>
  );
}


