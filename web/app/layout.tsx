import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sales Intelligence Platform",
  description:
    "Rank the companies most likely to need cybersecurity help, with the reason each one ranks.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
