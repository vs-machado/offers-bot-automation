import {
  Activity,
  CalendarClock,
  Check,
  Clock,
  FileText,
  Home,
  Link2,
  MessageSquareText,
  Rocket,
  Send,
  Settings,
  Sparkles,
  TrendingUp,
  UserCircle2,
  UsersRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { getServerSession } from "next-auth";
import Image from "next/image";
import { redirect } from "next/navigation";

import { authOptions } from "@/auth";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ThemeToggle } from "@/components/theme-toggle";
import {
  getDashboardUser,
  getDestinations,
  getUserConfigs,
} from "@/features/dashboard/api/dashboard-server";
import { LogoutButton } from "@/features/dashboard/components/LogoutButton";
import { MobileSidebar } from "@/features/dashboard/components/MobileSidebar";
import { SetupDialog } from "@/features/setup/SetupDialog";

type OnboardingStepId =
  | "connectedTelegram"
  | "addedFirstGroup"
  | "configuredAffiliates"
  | "selectedMessageTemplate"
  | "addedBotToGroup";

type OnboardingState = Record<OnboardingStepId, boolean>;

type OnboardingStep = {
  id: OnboardingStepId;
  title: string;
  shortTitle: string;
  description: string;
  icon: LucideIcon;
  color: string;
};

const defaultOnboardingState: OnboardingState = {
  connectedTelegram: false,
  addedFirstGroup: false,
  configuredAffiliates: false,
  selectedMessageTemplate: false,
  addedBotToGroup: false,
};

const onboardingSteps: OnboardingStep[] = [
  {
    id: "connectedTelegram",
    title: "Add platform Telegram bot",
    shortTitle: "Add bot",
    description: "Add @tgtestoffersbot to the destination where offers should appear.",
    icon: Send,
    color: "bg-sky-100 text-sky-600 dark:bg-sky-400/15 dark:text-sky-300",
  },
  {
    id: "addedFirstGroup",
    title: "Add your first group",
    shortTitle: "Add group",
    description: "Add the bot to the group or channel where offers should appear.",
    icon: UsersRound,
    color: "bg-emerald-100 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-300",
  },
  {
    id: "selectedMessageTemplate",
    title: "Add destination chat ID",
    shortTitle: "Add chat ID",
    description: "Paste the destination chat ID so we can verify bot posting access.",
    icon: MessageSquareText,
    color: "bg-orange-100 text-orange-600 dark:bg-orange-400/15 dark:text-orange-300",
  },
  {
    id: "configuredAffiliates",
    title: "Configure affiliate sources",
    shortTitle: "Configure affiliates",
    description: "Add affiliate sources and tracking settings.",
    icon: Link2,
    color: "bg-violet-100 text-violet-600 dark:bg-violet-400/15 dark:text-violet-300",
  },
  {
    id: "addedBotToGroup",
    title: "Choose source groups",
    shortTitle: "Choose sources",
    description: "Select which Telegram groups the bot should copy offers from.",
    icon: CalendarClock,
    color: "bg-blue-100 text-blue-600 dark:bg-blue-400/15 dark:text-blue-300",
  },
];

const setupBenefits: Array<{
  icon: LucideIcon;
  title: string;
  description: string;
  color: string;
}> = [
  {
    icon: Clock,
    title: "Save time",
    description: "Automate repetitive tasks",
    color: "bg-sky-100 text-sky-600 dark:bg-sky-400/15 dark:text-sky-300",
  },
  {
    icon: TrendingUp,
    title: "Increase earnings",
    description: "Publish more, earn more",
    color: "bg-emerald-100 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-300",
  },
  {
    icon: UsersRound,
    title: "Grow your audience",
    description: "Reach more people daily",
    color: "bg-violet-100 text-violet-600 dark:bg-violet-400/15 dark:text-violet-300",
  },
];

const sidebarItems: Array<{
  icon: LucideIcon;
  label: string;
  active?: boolean;
}> = [
  { icon: Home, label: "Home", active: true },
  { icon: MessageSquareText, label: "Messages" },
  { icon: CalendarClock, label: "Scheduled messages" },
  { icon: UsersRound, label: "Groups" },
  { icon: Link2, label: "Affiliate sources" },
  { icon: FileText, label: "Templates" },
  { icon: Settings, label: "Settings" },
];

const workflowSteps = [
  {
    title: "Use platform Telegram bot",
    description: "The app posts through @tgtestoffersbot, not your Telegram user account.",
    icon: UsersRound,
  },
  {
    title: "Add bot to destinations",
    description: "Make the bot admin in every group or channel where offers should be published.",
    icon: MessageSquareText,
  },
  {
    title: "Configure affiliate sources",
    description: "Add affiliate sources and tracking settings before offers go live.",
    icon: Sparkles,
  },
  {
    title: "Verify posting access",
    description: "Save the destination chat ID so the bot can publish there.",
    icon: Link2,
  },
];

const productionMetrics: Array<{
  label: string;
  value: string;
  icon: LucideIcon;
  accent: string;
  bar: string;
}> = [
  {
    label: "Messages posted",
    value: "128",
    icon: Send,
    accent: "bg-emerald-100 text-emerald-600 dark:bg-emerald-400/15 dark:text-emerald-300",
    bar: "bg-emerald-500",
  },
  {
    label: "Scheduled posts",
    value: "16",
    icon: CalendarClock,
    accent: "bg-sky-100 text-sky-600 dark:bg-sky-400/15 dark:text-sky-300",
    bar: "bg-sky-500",
  },
  {
    label: "Converted links",
    value: "94",
    icon: Link2,
    accent: "bg-violet-100 text-violet-600 dark:bg-violet-400/15 dark:text-violet-300",
    bar: "bg-violet-500",
  },
  {
    label: "Connected groups",
    value: "8",
    icon: UsersRound,
    accent: "bg-orange-100 text-orange-600 dark:bg-orange-400/15 dark:text-orange-300",
    bar: "bg-orange-500",
  },
];

/**
 * Small, self-contained styles for motion that doesn't depend on the
 * consumer's Tailwind config (keyframes + reduced-motion guard).
 */
function DashboardMotionStyles() {
  return (
    <style>{`
      @keyframes dash-float {
        0%, 100% { transform: translateY(0); }
        50% { transform: translateY(-8px); }
      }
      @keyframes dash-flow {
        to { background-position: 0 28px; }
      }
      @keyframes dash-step-in {
        from { opacity: 0; transform: translateY(8px) scale(.96); }
        to { opacity: 1; transform: translateY(0) scale(1); }
      }
      @keyframes dash-check-in {
        0% { opacity: 0; transform: scale(.55) rotate(-8deg); }
        70% { transform: scale(1.08) rotate(0); }
        100% { opacity: 1; transform: scale(1) rotate(0); }
      }
      @keyframes dash-pulse {
        0%, 100% { opacity: .45; transform: scale(1); }
        50% { opacity: 1; transform: scale(1.08); }
      }
      .dash-mascot-float { animation: dash-float 6s ease-in-out infinite; }
      .dash-flow-line {
        background-image: repeating-linear-gradient(
          to bottom,
          currentColor 0,
          currentColor 6px,
          transparent 6px,
          transparent 14px
        );
        background-size: 100% 28px;
        animation: dash-flow 1s linear infinite;
      }
      .dash-step-in { animation: dash-step-in .42s ease-out both; }
      .dash-check-in { animation: dash-check-in .28s ease-out both; }
      .dash-status-dot { animation: dash-pulse 2.2s ease-in-out infinite; }
      @media (prefers-reduced-motion: reduce) {
        .dash-mascot-float, .dash-flow-line, .dash-step-in, .dash-check-in, .dash-status-dot { animation: none; }
      }
    `}</style>
  );
}

function RobotMascot() {
  return (
    <div className="pointer-events-none relative h-36 w-[300px] md:h-44 md:w-[440px] xl:w-[520px]">
      <div className="dash-mascot-float absolute inset-0">
        <Image
          alt=""
          aria-hidden="true"
          className="relative h-full w-full object-contain object-right dark:opacity-90"
          height={864}
          priority
          src="/bot_image.png"
          width={1536}
        />
      </div>
    </div>
  );
}

function OperationalDashboard() {
  return (
    <div className="mt-6 space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {productionMetrics.map((metric) => {
          const Icon = metric.icon;

          return (
            <Card
              className="relative overflow-hidden border border-border bg-card py-0 shadow-[0_16px_50px_rgba(15,23,42,0.04)] transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_60px_rgba(15,23,42,0.08)] dark:border-white/10 dark:bg-white/[0.035] dark:shadow-[0_24px_80px_rgba(0,0,0,0.24)]"
              key={metric.label}
            >
              <div className={`absolute inset-x-0 top-0 h-1 ${metric.bar}`} />
              <CardContent className="flex items-center justify-between p-6">
                <div>
                  <p className="text-sm font-semibold text-muted-foreground">
                    {metric.label}
                  </p>
                  <p className="mt-2 text-3xl font-black text-card-foreground">
                    {metric.value}
                  </p>
                </div>
                <div className={`flex size-12 items-center justify-center rounded-2xl ${metric.accent}`}>
                  <Icon className="size-5" />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card className="border border-border bg-card py-0 shadow-[0_16px_50px_rgba(15,23,42,0.04)] dark:border-white/10 dark:bg-white/[0.035] dark:shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
        <CardHeader className="p-6 pb-2">
          <CardTitle className="text-2xl font-black tracking-tight">
            Recent activity
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Production workspace activity appears here after onboarding completes.
          </p>
        </CardHeader>
        <CardContent className="p-6 pt-4">
          <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border bg-muted/50 p-10 text-center">
            <div className="flex size-12 items-center justify-center rounded-full bg-primary/10 text-primary">
              <Send className="size-5" />
            </div>
            <div>
              <p className="text-sm font-semibold text-card-foreground">
                Nothing posted yet
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                Once your bot publishes an offer, it will show up here.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export async function Dashboard() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/");
  }

  const dbUser = await getDashboardUser(session.accessToken);
  const destinations = await getDestinations(session.accessToken);
  const configs = await getUserConfigs(session.accessToken);
  const hasEnabledDestination = destinations.some((destination) => destination.enabled);
  const hasAffiliateConfig = configs.some((config) =>
    ["amazon", "shopee", "mercado_livre", "aliexpress"].includes(config.config_type)
  );
  const hasSourceChatsConfig = configs.some((config) => {
    const sourceChats = config.config_data?.source_chats;
    return config.config_type === "source_chats" && Array.isArray(sourceChats) && sourceChats.length > 0;
  });
  const onboardingState: OnboardingState = {
    ...defaultOnboardingState,
    connectedTelegram: hasEnabledDestination,
    addedFirstGroup: hasEnabledDestination,
    selectedMessageTemplate: hasEnabledDestination,
    configuredAffiliates: hasAffiliateConfig,
    addedBotToGroup: hasSourceChatsConfig,
  };
  const dbFullName = dbUser?.full_name?.trim();
  const userEmail = dbUser?.email || session.user?.email || "Signed in";
  const userName = dbFullName || session.user?.name || userEmail || "Workspace user";
  const userInitial = (userName || userEmail || "U")
    .trim()
    .charAt(0)
    .toUpperCase();
  const completedCount = onboardingSteps.filter(
    (step) => onboardingState[step.id]
  ).length;
  const totalSteps = onboardingSteps.length;
  const allStepsCompleted = completedCount === totalSteps;
  const progressPercent = Math.round((completedCount / totalSteps) * 100);

  return (
    <main className="relative isolate min-h-[100dvh] overflow-x-clip bg-background text-foreground lg:h-[100dvh]">
      <DashboardMotionStyles />

      <aside className="hidden border-sidebar-border bg-sidebar p-4 text-sidebar-foreground lg:fixed lg:inset-y-0 lg:left-0 lg:z-20 lg:block lg:w-64 lg:border-r">
        <div className="flex h-full min-h-[calc(100dvh-2rem)] flex-col lg:min-h-0">
          <div className="flex items-center justify-between gap-3 px-2 py-2 text-sm font-bold tracking-tight">
            <div className="flex items-center gap-3">
              <Send className="size-6 fill-sidebar-primary text-sidebar-primary" />
              <span>TG OFFERS BOT</span>
            </div>
            <ThemeToggle />
          </div>

          <nav aria-label="Dashboard sections" className="mt-5 space-y-1.5">
            {sidebarItems.map((item) => {
              const Icon = item.icon;

              return (
                <Button
                  className={
                    item.active
                      ? "group h-12 w-full justify-start gap-4 bg-sidebar-primary/10 text-sm font-semibold text-sidebar-primary shadow-none hover:bg-sidebar-primary/15 dark:bg-sidebar-primary/18 dark:hover:bg-sidebar-primary/24"
                      : "group h-12 w-full justify-start gap-4 border-transparent bg-transparent text-sm font-medium text-muted-foreground shadow-none hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                  }
                  key={item.label}
                  type="button"
                  variant={item.active ? "default" : "outline"}
                >
                  <Icon className="size-5 transition-transform group-hover:scale-110" strokeWidth={1.9} />
                  <span>{item.label}</span>
                </Button>
              );
            })}
          </nav>

          <div className="mt-auto">
            <Separator className="my-4" />

            <div className="flex items-center gap-3 px-1">
              <div className="relative">
                <Avatar className="size-11 bg-sidebar-primary/15">
                  <AvatarFallback className="bg-sidebar-primary/15 font-semibold text-sidebar-primary">
                    {userInitial}
                  </AvatarFallback>
                </Avatar>
                <span className="absolute -bottom-0.5 -right-0.5 block size-3 rounded-full border-2 border-sidebar bg-emerald-500" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-sidebar-foreground">{userName}</p>
                <p className="truncate text-xs text-muted-foreground">{userEmail}</p>
              </div>
              <UserCircle2 className="size-5 text-muted-foreground" />
            </div>

            <Separator className="my-4" />
            <div className="[&_button]:text-muted-foreground">
              <LogoutButton />
            </div>
          </div>
        </div>
      </aside>

      <section className="relative pb-8 lg:ml-64 lg:h-[100dvh] lg:overflow-y-auto lg:px-7 lg:py-4">
        <div className="sticky top-0 z-20 flex h-14 items-center justify-between border-b border-border bg-background/95 px-4 backdrop-blur lg:hidden">
          <div className="flex min-w-0 items-center gap-2">
            <MobileSidebar
              userEmail={userEmail}
              userInitial={userInitial}
              userName={userName}
            />
            <div className="flex min-w-0 items-center gap-2 text-sm font-bold tracking-tight">
              <Send className="size-5 shrink-0 fill-primary text-primary" />
              <span className="truncate">TG OFFERS BOT</span>
            </div>
          </div>
          <ThemeToggle />
        </div>

        <div className="px-4 pt-5 lg:px-0 lg:pt-0">
        <header className="relative pb-6 pr-0 md:min-h-36 md:pr-[300px] lg:min-h-40 lg:pr-[360px] xl:pr-[470px]">
          <div className="relative z-10 pt-1">
            <h1 className="text-2xl font-semibold tracking-tight text-foreground sm:text-3xl md:text-[2.1rem]">
              Good morning, {userName}! <span aria-hidden="true">👋</span>
            </h1>
            <p className="mt-2 max-w-md text-base text-muted-foreground">
              {allStepsCompleted
                ? "Your bot is live and posting offers to your groups automatically."
                : "Finish setup and your bot starts posting offers on its own."}
            </p>
            <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-border bg-muted/50 px-3 py-1.5 text-xs font-semibold text-muted-foreground">
              {allStepsCompleted ? (
                <>
                  <Activity className="dash-status-dot size-3.5 text-emerald-600 dark:text-emerald-300" />
                  <span className="text-card-foreground">Bot is live</span>
                </>
              ) : (
                <>
                  {completedCount} of {totalSteps} setup steps done
                </>
              )}
            </div>
          </div>
          <div className="absolute right-0 top-0 hidden md:block">
            <RobotMascot />
          </div>
        </header>

        {allStepsCompleted ? (
          <OperationalDashboard />
        ) : (
          <>
            <Card className="border border-border bg-card py-0 shadow-sm dark:bg-white/[0.025]">
              <CardContent className="grid gap-6 p-5 sm:p-6 xl:grid-cols-[200px_1fr] xl:items-center 2xl:grid-cols-[200px_1fr_auto]">
                <div>
                  <CardTitle className="text-2xl font-semibold tracking-tight">
                    Let&apos;s set up your bot
                  </CardTitle>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Complete these steps to publish your first automated offer.
                  </p>
                  <p className="mt-6 text-sm font-semibold text-card-foreground">
                    Your progress
                  </p>
                  <div className="mt-2 flex items-baseline gap-2">
                    <p className="text-3xl font-bold text-foreground">
                      {completedCount} of {totalSteps}
                    </p>
                    <span className="text-sm font-semibold text-primary">
                      {progressPercent}%
                    </span>
                  </div>
                  <div className="mt-3 h-2 w-full max-w-52 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-700 ease-out dark:bg-primary/75"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-5 gap-2 sm:gap-4 xl:gap-5">
                  {onboardingSteps.map((step, index) => {
                    const isCompleted = onboardingState[step.id];
                    const previousCompleted =
                      index > 0 && onboardingState[onboardingSteps[index - 1].id];

                    return (
                      <div
                        className="dash-step-in relative text-center"
                        key={step.id}
                        style={{ animationDelay: `${index * 70}ms` }}
                      >
                        {index > 0 ? (
                          <div className="absolute left-[-50%] right-1/2 top-[18px] h-0.5 overflow-hidden bg-muted sm:top-5 sm:h-1">
                            <span
                              className={
                                previousCompleted
                                  ? "block h-full w-full origin-left scale-x-100 bg-primary transition-transform duration-700 ease-out"
                                  : "block h-full w-full origin-left scale-x-0 bg-primary transition-transform duration-700 ease-out"
                              }
                            />
                          </div>
                        ) : null}
                        <div
                          className={
                            isCompleted
                              ? "relative z-10 mx-auto flex size-9 items-center justify-center rounded-full bg-primary text-xs font-bold text-primary-foreground transition duration-300 sm:size-11 sm:text-sm"
                              : "relative z-10 mx-auto flex size-9 items-center justify-center rounded-full border border-border bg-card text-xs font-bold text-foreground transition duration-300 sm:size-11 sm:text-sm"
                          }
                        >
                          {isCompleted ? <Check className="dash-check-in size-5" /> : index + 1}
                        </div>
                        <p className="mt-2 text-[11px] font-semibold leading-4 text-card-foreground sm:mt-4 sm:text-sm">
                          {step.shortTitle}
                        </p>
                      </div>
                    );
                  })}
                </div>

                <div className="w-full [&>div]:max-w-none [&>div>button]:w-full sm:[&>div>button]:w-[172px] xl:col-span-2 xl:justify-self-end 2xl:col-span-1">
                  <SetupDialog
                    configs={configs}
                    destinations={destinations}
                    hasEnabledDestination={hasEnabledDestination}
                  />
                </div>
              </CardContent>
            </Card>

            <div className="mt-4 grid items-stretch gap-4 xl:grid-cols-2">
              <Card className="h-full border border-border bg-card py-0 shadow-sm dark:bg-white/[0.025] xl:grid xl:grid-cols-[minmax(0,0.95fr)_minmax(340px,1.05fr)] xl:items-stretch">
                <div className="flex flex-col">
                  <CardHeader className="p-6 pb-2">
                    <div className="flex items-center gap-3">
                      <Sparkles className="size-5 text-primary" />
                      <CardTitle className="text-2xl font-semibold tracking-tight">
                        How your bot works
                      </CardTitle>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      Your bot automatically finds, formats and posts offers for you.
                    </p>
                  </CardHeader>
                  <CardContent className="flex flex-1 items-center p-6 pt-4">
                    <div className="w-full space-y-2">
                    {workflowSteps.map((step, index) => {
                      const Icon = step.icon;

                      const iconColor = onboardingSteps[index]?.color ?? onboardingSteps[0].color;

                      return (
                        <div className="-mx-3 flex min-h-[72px] items-center gap-4 p-3" key={step.title}>
                          <div className="relative flex size-12 shrink-0 items-center justify-center">
                            <div className={`flex size-12 items-center justify-center rounded-2xl ${iconColor}`}>
                              <Icon className="size-5" strokeWidth={2} />
                            </div>
                            {index < workflowSteps.length - 1 ? (
                              <div className="dash-flow-line absolute top-[calc(100%+0.5rem)] h-6 w-px text-emerald-500/70 dark:text-emerald-300/70" />
                            ) : null}
                          </div>
                          <div className="min-w-0 flex-1">
                            <h3 className="font-semibold text-card-foreground">
                              {index + 1}. {step.title}
                            </h3>
                            <p className="mt-1 text-sm leading-6 text-muted-foreground">
                              {step.description}
                            </p>
                          </div>
                        </div>
                        );
                      })}
                    </div>
                  </CardContent>
                </div>

                <div className="hidden min-h-[500px] items-center justify-center p-4 pt-12 md:flex xl:min-h-[560px] xl:pt-16">
                  <Image
                    alt="How the bot clones offers, converts links, and publishes them to your groups"
                    className="h-auto max-h-full w-full scale-110 object-contain object-center dark:opacity-90"
                    height={1024}
                    loading="eager"
                    src="/how_it_works.png"
                    width={1536}
                  />
                </div>
              </Card>

              <Card className="scroll-mt-6 h-full border border-border bg-card py-0 shadow-sm dark:bg-white/[0.025]" id="setup-checklist">
                <CardHeader className="flex flex-col gap-4 p-6 pb-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <CardTitle className="text-2xl font-semibold tracking-tight">
                      Setup checklist
                    </CardTitle>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Complete steps below to activate your automation.
                    </p>
                  </div>
                </CardHeader>
                <CardContent className="flex flex-1 flex-col justify-center p-6 pt-4">
                  <div className="space-y-2">
                    {onboardingSteps.map((step) => {
                      const Icon = step.icon;
                      const isCompleted = onboardingState[step.id];

                      return (
                        <div
                          className="group -mx-3 flex items-start gap-3 rounded-lg p-3 sm:items-center sm:gap-4"
                          key={step.id}
                        >
                          <div
                            className={`flex size-10 shrink-0 items-center justify-center rounded-lg transition-transform duration-200 group-hover:scale-105 sm:size-12 ${step.color}`}
                          >
                            <Icon className="size-5" strokeWidth={2} />
                          </div>
                          <div className="min-w-0 flex-1">
                            <h3 className="font-semibold text-card-foreground">
                              {step.title}
                            </h3>
                            <p className="mt-1 text-sm text-muted-foreground">
                              {step.description}
                            </p>
                            <span className="mt-2 inline-flex rounded-md bg-muted px-2 py-1 text-[11px] font-semibold text-muted-foreground sm:hidden">
                              {isCompleted ? "Completed" : "Not started"}
                            </span>
                          </div>
                          <span
                            className={
                              isCompleted
                                ? "hidden shrink-0 rounded-md bg-primary/15 px-3 py-1.5 text-xs font-semibold text-primary sm:inline-flex"
                                : "hidden shrink-0 rounded-md bg-muted px-3 py-1.5 text-xs font-semibold text-muted-foreground sm:inline-flex"
                            }
                          >
                            {isCompleted ? "Completed" : "Not started"}
                          </span>
                        </div>
                      );
                    })}
                  </div>

                </CardContent>
              </Card>
            </div>

            <Card className="relative mt-4 overflow-hidden border border-border bg-card py-0 shadow-sm dark:bg-white/[0.025]">
              <CardContent className="grid gap-6 p-6 md:grid-cols-[auto_1fr] lg:grid-cols-[auto_1fr] xl:grid-cols-[auto_1fr_repeat(3,minmax(0,1fr))] xl:items-center">
                <div className="relative flex size-20 shrink-0 items-center justify-center justify-self-center lg:justify-self-start">
                  <span className="absolute size-20 rounded-full border border-primary/15" />
                  <span
                    className="dash-status-dot absolute size-14 rounded-full border border-emerald-400/35"
                    style={{ animationDelay: "0.5s" }}
                  />
                  <div className="relative flex size-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-500 dark:bg-emerald-400/20 dark:text-emerald-300">
                    <Rocket className="size-7" />
                  </div>
                </div>
                <div>
                  <h2 className="text-2xl font-semibold tracking-tight text-card-foreground">
                    Ready to go live!
                  </h2>
                  <p className="mt-2 text-base leading-7 text-muted-foreground">
                    Finish setup to start scheduling and publishing offers automatically.
                  </p>
                </div>
                {setupBenefits.map((benefit) => {
                  const Icon = benefit.icon;

                  return (
                    <div className="flex items-center gap-4" key={benefit.title}>
                      <div className={`flex size-12 shrink-0 items-center justify-center rounded-2xl ${benefit.color}`}>
                        <Icon className="size-5" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-card-foreground">
                          {benefit.title}
                        </h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          {benefit.description}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </CardContent>
            </Card>
          </>
        )}
        </div>
      </section>
    </main>
  );
}
