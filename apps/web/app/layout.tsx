import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "SendPilot",
  description: "Sales & email AI agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav>
          <Link className="brand" href="/">SendPilot</Link>
          <Link href="/connections">Connections</Link>
          <Link href="/documents">Documents</Link>
        </nav>
        <div className="container">{children}</div>
      </body>
    </html>
  );
}
