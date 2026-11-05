import type { Metadata } from "next";
import { ShellGate } from "@/components/shell/ShellGate";
import { COMPANY, PRODUCT, PRODUCT_TAGLINE } from "@/lib/brand";
import "./globals.css";

export const metadata: Metadata = {
  title: `${PRODUCT} · ${COMPANY}`,
  description: PRODUCT_TAGLINE,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ar" dir="rtl">
      <body>
        <ShellGate>{children}</ShellGate>
      </body>
    </html>
  );
}
