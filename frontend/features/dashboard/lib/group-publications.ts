import type { Delivery, Publication } from "@/features/dashboard/types";

export function groupPublications(deliveries: Delivery[]): Publication[] {
  const publications = new Map<string, Publication>();
  for (const delivery of deliveries) {
    const id = delivery.offer_id || delivery.id;
    const publication = publications.get(id);
    if (publication) publication.deliveries.push(delivery);
    else publications.set(id, { id, deliveries: [delivery] });
  }
  return [...publications.values()];
}
