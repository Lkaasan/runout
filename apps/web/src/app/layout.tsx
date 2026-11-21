import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Album Deep-Dive",
  description: "Sit-down album listening with sourced context.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
