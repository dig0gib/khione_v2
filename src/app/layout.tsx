import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Khione | 양자 트레이딩 대시보드",
  description: "초고성능 AI 자동매매 터미널",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
