import { LayoutDashboard, Link2, Radio, UsersRound } from "lucide-react";

export const workspaceNavigation = [
  {
    icon: LayoutDashboard,
    label: "Visão geral",
    href: "/dashboard",
  },
  {
    icon: UsersRound,
    label: "Destinos",
    href: "/settings/destinations",
  },
  {
    icon: Radio,
    label: "Origens de ofertas",
    href: "/settings/sources",
  },
  {
    icon: Link2,
    label: "Afiliados",
    href: "/settings/affiliates",
  },
];
