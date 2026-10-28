import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "LolixCopilot — From raw footage to a stronger cut",
  description:
    "AI creative copilot for independent video editors and short-form creators. Turns raw footage into a structured editing blueprint.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full dark`}
    >
      <body className="min-h-full flex flex-col bg-[#0a0c0f] text-[#f3f4f6] selection:bg-[#e6ff00] selection:text-black antialiased">
        {children}
      </body>
    </html>
  );
}
