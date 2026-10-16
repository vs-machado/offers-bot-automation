export type SourceGroup = {
  id: string;
  label: string;
  messages?: SourceMessage[];
};

export type SourceMessage = {
  id: number;
  text: string;
  image_url?: string;
  post_url?: string;
  links?: Array<{
    text?: string;
    url: string;
  }>;
};
