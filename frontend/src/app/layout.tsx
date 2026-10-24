import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "SEOPilot — Your next move in search", description: "Evidence-backed website audits and recommendations you control." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
