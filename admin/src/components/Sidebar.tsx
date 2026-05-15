"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/reviews", label: "Reviews" },
  { href: "/posts", label: "Posts" },
  { href: "/reports", label: "Reports" },
  { href: "/places", label: "Places" },
  { href: "/users", label: "Users" },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem("admin_token");
    router.push("/login");
  };

  return (
    <aside className="w-56 min-h-screen bg-white border-r border-gray-200 flex flex-col">
      <div className="px-6 py-5 border-b border-gray-100">
        <span className="font-bold text-lg text-pink-600">Pinstagram</span>
        <span className="block text-xs text-gray-400 mt-0.5">Admin</span>
      </div>
      <nav className="flex-1 py-4">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={`flex items-center px-6 py-2.5 text-sm font-medium rounded-lg mx-2 mb-1 transition-colors ${
              pathname === n.href
                ? "bg-pink-50 text-pink-600"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            {n.label}
          </Link>
        ))}
      </nav>
      <div className="px-4 py-4 border-t border-gray-100">
        <button
          onClick={handleLogout}
          className="w-full text-sm text-red-500 hover:text-red-700 font-medium py-2 text-left px-2"
        >
          Log out
        </button>
      </div>
    </aside>
  );
}
