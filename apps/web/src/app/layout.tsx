import type { Metadata } from "next";
import { AppStartup } from "@/components/AppStartup";
import "./globals.css";

export const metadata: Metadata = {
  title: "Site Companion",
  description:
    "Verify policy information across connected systems before taking action.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <AppStartup>{children}</AppStartup>
      </body>
    </html>
  );
}
