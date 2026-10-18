import { type ReactNode } from "react";

import { Footer } from "./Footer";
import { Header } from "./Header";
import { Sidebar } from "./Sidebar";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-full flex flex-col">
      <Header />
      <div className="flex-1 flex max-w-screen-2xl w-full mx-auto">
        <Sidebar />
        <main className="flex-1 px-6 py-6 min-w-0">{children}</main>
      </div>
      <Footer />
    </div>
  );
}
