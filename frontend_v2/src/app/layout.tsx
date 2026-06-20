import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Trinetra HQ",
  description: "Traffic Intelligence Dashboard",
};

import { Suspense } from "react";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-bg-base text-text-primary flex min-h-screen`}>
        <Suspense fallback={<div className="w-72 border-r border-border bg-bg-surface h-screen fixed left-0 top-0"></div>}>
          <Sidebar />
        </Suspense>
        <main className="flex-1 ml-72 min-h-screen">
          {children}
        </main>
      </body>
    </html>
  );
}
