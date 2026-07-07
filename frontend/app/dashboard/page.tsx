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

import { LogoutButton } from "./logout-button";
import { SetupDialog } from "./setup-dialog";

const apiBaseUrl =
  process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

type DashboardUser = {
  email: string;
  full_name?: string | null;
};

async function getDashboardUser(
  accessToken?: string
): Promise<DashboardUser | null> {
  if (!accessToken) {
    return null;
  }

  try {
    const response = await fetch(`${apiBaseUrl}/users/me`, {
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as DashboardUser;
  } catch {
    return null;
  }
}

type OnboardingStep = {
  id: keyof typeof mockedOnboardingState.steps;
  title: string;
  shortTitle: string;
  description: string;
  icon: LucideIcon;
  color: string;
};

const mockedOnboardingState = {
  steps: {
    connectedTelegram: false,
    addedFirstGroup: false,
    configuredAffiliates: false,
    selectedMessageTemplate: false,
    addedBotToGroup: false,
  },
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
    id: "configuredAffiliates",
    title: "Configure affiliate sources",
    shortTitle: "Configure affiliates",
    description: "Add affiliate sources and tracking settings.",
    icon: Link2,
    color: "bg-violet-100 text-violet-600 dark:bg-violet-400/15 dark:text-violet-300",
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
    id: "addedBotToGroup",
    title: "Send a test offer",
    shortTitle: "Test posting",
    description: "Confirm the bot can publish before automation goes live.",
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
    title: "Verify posting access",
    description:
      "Save the destination chat ID. Backend checks the bot can post before enabling it.",
    icon: Link2,
  },
  {
    title: "Offers are published instantly",
    description: "The bot posts final messages to verified Telegram destinations.",
    icon: Send,
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
      .dash-status-dot { animation: dash-pulse 2.2s ease-in-out infinite; }
      @media (prefers-reduced-motion: reduce) {
        .dash-mascot-float, .dash-flow-line, .dash-status-dot { animation: none; }
      }
    `}</style>
  );
}

function RobotMascot() {
  return (
    <div className="pointer-events-none relative h-36 w-[300px] md:h-44 md:w-[440px] xl:w-[520px]">
      <div className="dash-mascot-float absolute inset-0">
        <div className="absolute right-10 top-1/2 -z-10 size-40 -translate-y-1/2 rounded-full bg-primary/20 blur-3xl dark:bg-primary/10" />
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

export default async function DashboardPage() {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect("/");
  }

  const dbUser = await getDashboardUser(session.accessToken);
  const dbFullName = dbUser?.full_name?.trim();
  const userEmail = dbUser?.email || session.user?.email || "Signed in";
  const userName = dbFullName || session.user?.name || userEmail || "Workspace user";
  const userInitial = (userName || userEmail || "U")
    .trim()
    .charAt(0)
    .toUpperCase();
  const completedCount = onboardingSteps.filter(
    (step) => mockedOnboardingState.steps[step.id]
  ).length;
  const totalSteps = onboardingSteps.length;
  const allStepsCompleted = completedCount === totalSteps;
  const progressPercent = Math.round((completedCount / totalSteps) * 100);

  return (
    <main className="relative isolate min-h-[100dvh] overflow-hidden bg-background text-foreground lg:h-[100dvh]">
      <DashboardMotionStyles />

      <aside className="hidden border-sidebar-border bg-sidebar/95 p-4 text-sidebar-foreground shadow-[12px_0_40px_rgba(15,23,42,0.04)] backdrop-blur dark:shadow-[18px_0_60px_rgba(0,0,0,0.28)] lg:fixed lg:inset-y-0 lg:left-0 lg:z-20 lg:block lg:w-[292px] lg:border-r">
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

      <section className="relative px-4 py-5 lg:ml-[292px] lg:h-[100dvh] lg:overflow-y-auto lg:px-7 lg:py-4">
        <header className="relative min-h-36 pr-0 lg:min-h-40 lg:pr-[360px] xl:pr-[470px]">
          <div className="relative z-10 pt-1">
            <h1 className="text-3xl font-semibold tracking-tight text-foreground md:text-[2.1rem]">
              Good morning, {userName}! <span aria-hidden="true">👋</span>
            </h1>
            <p className="mt-2 max-w-md text-base text-muted-foreground">
              {allStepsCompleted
                ? "Your bot is live and posting offers to your groups automatically."
                : "Finish setup and your bot starts posting offers on its own."}
            </p>
            <div className="mt-4 inline-flex items-center gap-2 rounded-full border border-border bg-card/80 px-3 py-1.5 text-xs font-semibold text-muted-foreground shadow-sm backdrop-blur">
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
            <Card className="mt-2 border border-border bg-card py-0 shadow-[0_16px_50px_rgba(15,23,42,0.04)] dark:border-white/10 dark:bg-white/[0.035] dark:shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
              <CardContent className="grid gap-7 p-6 xl:grid-cols-[220px_1fr] xl:items-center 2xl:grid-cols-[220px_1fr_auto]">
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
                  <div className="mt-3 h-3 w-full max-w-52 overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-primary transition-all duration-700 ease-out"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>

                <div className="grid gap-5 sm:grid-cols-5 lg:gap-4 xl:gap-5">
                  {onboardingSteps.map((step, index) => {
                    const isCompleted = mockedOnboardingState.steps[step.id];
                    const previousCompleted =
                      index > 0 && mockedOnboardingState.steps[onboardingSteps[index - 1].id];

                    return (
                      <div className="relative text-center" key={step.id}>
                        {index > 0 ? (
                          <div
                            className={`absolute left-[-50%] right-1/2 top-5 hidden h-px transition-colors duration-500 sm:block ${
                              previousCompleted ? "bg-primary" : "bg-border"
                            }`}
                          />
                        ) : null}
                        <div
                          className={
                            isCompleted
                              ? "relative mx-auto flex size-11 items-center justify-center rounded-full bg-primary text-sm font-bold text-primary-foreground shadow-[0_0_24px_rgba(16,185,129,0.22)]"
                              : "relative mx-auto flex size-11 items-center justify-center rounded-full border border-border bg-card text-sm font-bold text-foreground"
                          }
                        >
                          {isCompleted ? <Check className="size-5" /> : index + 1}
                        </div>
                        <p className="mt-4 text-sm font-semibold text-card-foreground">
                          {step.shortTitle}
                        </p>
                      </div>
                    );
                  })}
                </div>

                <div className="xl:col-span-2 xl:justify-self-end 2xl:col-span-1">
                  <SetupDialog />
                </div>
              </CardContent>
            </Card>

            <div className="mt-5 grid items-stretch gap-5 xl:grid-cols-2">
              <Card className="h-full border border-border bg-card py-0 shadow-[0_16px_50px_rgba(15,23,42,0.04)] dark:border-white/10 dark:bg-white/[0.035] dark:shadow-[0_24px_80px_rgba(0,0,0,0.24)] xl:grid xl:grid-cols-[minmax(0,0.95fr)_minmax(340px,1.05fr)] xl:items-stretch">
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

              <Card className="scroll-mt-6 h-full border border-border bg-card py-0 shadow-[0_16px_50px_rgba(15,23,42,0.04)] dark:border-white/10 dark:bg-white/[0.035] dark:shadow-[0_24px_80px_rgba(0,0,0,0.24)]" id="setup-checklist">
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
                      const isCompleted = mockedOnboardingState.steps[step.id];

                      return (
                        <div
                          className="group -mx-3 flex items-center gap-4 rounded-2xl p-3"
                          key={step.id}
                        >
                          <div
                            className={`flex size-12 shrink-0 items-center justify-center rounded-2xl transition-transform duration-200 group-hover:scale-105 ${step.color}`}
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
                          </div>
                          <span
                            className={
                              isCompleted
                                ? "shrink-0 rounded-xl bg-primary/15 px-4 py-2 text-xs font-semibold text-primary"
                                : "shrink-0 rounded-xl bg-muted px-4 py-2 text-xs font-semibold text-muted-foreground"
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

            <Card className="relative mt-5 overflow-hidden border border-border bg-card py-0 shadow-[0_16px_50px_rgba(15,23,42,0.04)] dark:border-white/10 dark:bg-white/[0.035] dark:shadow-[0_24px_80px_rgba(0,0,0,0.24)]">
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
      </section>
    </main>
  );
}
