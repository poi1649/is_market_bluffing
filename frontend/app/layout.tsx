import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Is Market Bluffing",
  description: "Detect overreaction and recovery patterns in US listed stocks",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
