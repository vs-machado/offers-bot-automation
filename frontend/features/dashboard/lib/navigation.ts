import { LayoutDashboard, Link2, Settings, UsersRound } from "lucide-react";

export const dashboardNavigation = [
  {
    icon: LayoutDashboard,
    label: "Visão geral",
    href: "/dashboard",
    active: true,
  },
  {
    icon: UsersRound,
    label: "Destinos",
    href: "/settings#destinations",
    active: false,
  },
  {
    icon: Link2,
    label: "Afiliados",
    href: "/settings#affiliates",
    active: false,
  },
  { icon: Settings, label: "Configurações", href: "/settings", active: false },
];
