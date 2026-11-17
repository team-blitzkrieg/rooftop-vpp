import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Household forecast",
  description: "Next 48 hours of PV, demand and net load. Read only.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
