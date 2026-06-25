// SPDX-License-Identifier: Apache-2.0
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "LectureVoice",
  description: "AI lecture video generator with voice cloning",
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
