export type AdminSourceGroup = {
  id: number;
  url: string;
  label: string;
  enabled: boolean;
};

export type SourceGroupInput = Omit<AdminSourceGroup, "id">;
