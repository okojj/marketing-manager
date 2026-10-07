import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "AI Marketing Manager", description: "브랜드를 이해하는 AI 마케팅 워크스페이스" };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ko"><body>{children}</body></html>;
}
