import { TopNav } from "@/components/TopNav";
import { Outlet } from "react-router-dom";

export default function AppLayout() {
  return (
    <div className="relative min-h-screen flex flex-col">
      <TopNav />
      <main className="flex-1 min-h-0">
        <Outlet />
      </main>
    </div>
  );
}
