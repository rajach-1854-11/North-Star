import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";
import { inter, lexend, jet } from "./fonts";

export const metadata: Metadata = { title: "North Star", description: "Professional instrument for experts." };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${lexend.variable} ${jet.variable}`}>
      <body className="bg-deep text-text"><Providers>{children}</Providers></body>
    </html>
  );
}
