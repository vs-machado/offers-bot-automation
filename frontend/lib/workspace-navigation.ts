import { LayoutDashboard, Link2, Settings, UsersRound } from "lucide-react";

export const workspaceNavigation = [
  {
    icon: LayoutDashboard,
    label: "Visão geral",
    href: "/dashboard",
  },
  {
    icon: UsersRound,
    label: "Destinos",
    href: "/settings#destinations",
  },
  {
    icon: Link2,
    label: "Afiliados",
    href: "/settings#affiliates",
  },
  { icon: Settings, label: "Configurações", href: "/settings" },
];
