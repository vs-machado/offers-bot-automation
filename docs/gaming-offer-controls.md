# Gaming-offer reduction

Open **Settings → Destinations → Reduzir ofertas gamer**. Choose the percentage
of gaming offers to retain for WhatsApp and Telegram independently. Expand
**Personalizar por grupo ou canal** to override the platform default for an owned
destination. An inherited rule also applies to newly added destinations.

- `100%`: no reduction (default when no policy exists).
- `25%`: keep approximately one quarter, reducing gaming offers by about 75%.
- `0%`: block gaming offers.
- Other categories continue to follow their existing destination/category rules.

This is deterministic product sampling, not a daily quota. The same product is
not rerolled on retries, source reposts, price changes, or restarts. Platform rules
make the same selection across that user's destinations unless overridden.
Selection uses the normalized product key when available, otherwise its normalized
title; different titles for an unidentified product can produce different selections.
Small samples can differ from the configured percentage. A filtered offer is
discarded, never held for later or used to fill a burst slot.

The existing parser classifies each product's `is_gaming` flag without an extra
LLM call. Gaming includes video games, consoles, GPUs, gaming computers and
gaming-specific peripherals/furniture. Explicit gaming title signals provide a
fallback, including older queued offers. Ordinary office laptops, generic
RAM/storage, phones, TVs and board games are not automatically gaming.

Policies are encrypted in the existing `user_configs` table under `gaming_policy`;
no schema migration is needed. Authenticated `GET/PUT /users/me/gaming-policy`
permit integer percentages from 0 through 100, and destination overrides must
belong to the authenticated user. Removing an override restores inheritance.

Workers check the current policy before queue admission and before sending,
including after deferral. Queue-time filtering logs `Gaming offer filtered`;
previously queued offers rejected by a new policy are cancelled with
`gaming_reduced`. Category checks, expiration, deduplication, WhatsApp quotas,
burst trimming and pauses continue to apply. API, reader, posting workers and
frontend must be updated together to preserve queued gaming metadata.

## Initial account tuning

Read-only audit for the requested account on November 14, 2026 found 64 clearly
gaming titles per WhatsApp destination over 24 hours: 64/278 channel posts (23.0%)
and 64/284 group posts (22.5%). Over 72 hours the corresponding shares were
193/859 (22.5%) and 196/899 (21.8%). Counts used explicit gaming title indicators;
generic PC hardware was not automatically counted as gaming.

Retaining 25% targets roughly 16 gaming posts per destination/day at that traffic,
or about 7% of the resulting feed before other delivery controls. This is an
estimate rather than a guaranteed cap. The initial requested setup uses this
WhatsApp default and retains all Telegram gaming offers.
