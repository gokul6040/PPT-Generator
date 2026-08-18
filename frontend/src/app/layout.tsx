import type { Metadata } from "next";
import { Geist } from "next/font/google";
import { TeamsInitializer } from "@/components/TeamsInitializer";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TurnB Case Study PPT Agent",
  description:
    "Build TurnB case study presentations from rough project content.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} h-full antialiased`}>
      <body className="h-dvh overflow-hidden">
        <TeamsInitializer />
        {children}
      </body>
    </html>
  );
}
