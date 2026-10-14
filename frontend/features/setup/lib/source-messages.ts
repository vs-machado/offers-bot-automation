import type { SourceGroup, SourceMessage } from "@/features/setup/types";

export function getSourceDisplayLabel(group: SourceGroup) {
  const sourceOption = group.label.match(/^Source option (\d+)$/);
  if (sourceOption?.[1]) {
    return `Grupo ${sourceOption[1]}`;
  }

  const customSource = group.label.match(/^Custom source (\d+)$/);
  if (customSource?.[1]) {
    return `Grupo personalizado ${customSource[1]}`;
  }

  return group.label;
}

export function getHiddenMessageLinks(message: SourceMessage) {
  return (message.links ?? []).filter(
    (link) => link.url && !message.text.includes(link.url)
  );
}
