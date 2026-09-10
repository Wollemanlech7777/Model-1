import type { Metadata } from "next";
import { AppStartup } from "@/components/AppStartup";
import "./globals.css";

export const metadata: Metadata = {
  title: "Site Companion",
  description:
    "Verify policy information across connected systems before taking action.",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "any" },
      { url: "/icon.svg", type: "image/svg+xml" },
    ],
    apple: [{ url: "/apple-icon.png" }],
  },
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
