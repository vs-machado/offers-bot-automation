import { LayoutDashboard, Link2, Radio, Send, ShieldCheck, Sparkles, UsersRound } from "lucide-react";

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
  {
    icon: Sparkles,
    label: "Modelos de IA",
    href: "/settings/models",
  },
];

export const adminNavigation = [
  { icon: ShieldCheck, label: "Administração", href: "/admin/source-groups" },
  { icon: Send, label: "Publicação no X", href: "/admin/x-buffer" },
];
