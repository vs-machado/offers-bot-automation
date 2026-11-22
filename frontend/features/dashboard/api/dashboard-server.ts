import "server-only";

import type { DashboardUser, DeliveryHistoryData } from "@/features/dashboard/types";
import type { ConfigSummary, DestinationSummary } from "@/shared/contracts/user-config";

const apiBaseUrl =
  process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

async function getAuthenticated<T>(path: string, accessToken?: string): Promise<T | null> {
  if (!accessToken) {
    return null;
  }

  try {
    const response = await fetch(`${apiBaseUrl}${path}`, {
      cache: "no-store",
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      return null;
    }

    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export async function getDashboardUser(accessToken?: string) {
  return getAuthenticated<DashboardUser>("/users/me", accessToken);
}

export async function getDeliveryHistory(accessToken?: string) {
  return getAuthenticated<DeliveryHistoryData>("/users/me/deliveries?group_by_offer=true", accessToken);
}

export async function getDestinations(accessToken?: string) {
  return (await getAuthenticated<DestinationSummary[]>(
    "/users/me/destinations",
    accessToken
  )) ?? [];
}

export async function getUserConfigs(accessToken?: string) {
  return (await getAuthenticated<ConfigSummary[]>("/users/me/configs", accessToken)) ?? [];
}
