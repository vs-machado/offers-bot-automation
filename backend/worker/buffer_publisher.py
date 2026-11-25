"""Send a single fresh offer to an explicitly configured Buffer X channel."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import logging
import os
import re
from urllib.parse import urlsplit

import httpx

LOGGER = logging.getLogger(__name__)
ENDPOINT = "https://api.buffer.com"
CHANNEL_QUERY = """query OfferChannel($id: ChannelId!) {
  channel(input: {id: $id}) { id name service isLocked isDisconnected isQueuePaused }
}"""
POSTS_CHANNEL = """query PostsChannel($id: ChannelId!) {
  channel(input: {id: $id}) { id service organizationId }
}"""
RECENT_POSTS = """query RecentXPosts($input: PostsInput!) {
  posts(first: 6, input: $input) {
    edges { node { id channelId text status sentAt externalLink } }
  }
}"""
CREATE_POST = """mutation ShareOffer($input: CreatePostInput!) {
  createPost(input: $input) {
    __typename
    ... on PostActionSuccess { post { id status } }
    ... on MutationError { message }
  }
}"""


@dataclass(frozen=True)
class BufferPublisher:
    token: str = field(repr=False)
    channel_id: str

    @classmethod
    def from_env(cls):
        """Load the personal Buffer key and explicit X channel ID from worker settings."""
        token = os.getenv("X_OFFERS_BUFFER_API_KEY", "").strip()
        channel_id = os.getenv("X_OFFERS_BUFFER_CHANNEL_ID", "").strip()
        if not token or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", channel_id):
            raise ValueError(
                "Set X_OFFERS_BUFFER_API_KEY and X_OFFERS_BUFFER_CHANNEL_ID"
            )
        return cls(token, channel_id)

    def _graphql(self, query, variables):
        response = httpx.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {self.token}"},
            json={"query": query, "variables": variables},
            timeout=httpx.Timeout(8, connect=3),
            follow_redirects=False,
        )
        response.raise_for_status()
        return response.json()["data"]

    def check_connection(self) -> str | None:
        """Read the connected X account name without sending a post."""
        try:
            channel = self._graphql(CHANNEL_QUERY, {"id": self.channel_id})["channel"]
            if (
                channel["id"] != self.channel_id
                or channel["service"] != "twitter"
                or channel["isLocked"] is not False
                or channel["isDisconnected"] is not False
                or channel["isQueuePaused"] is not False
            ):
                return None
            return channel.get("name") or channel["id"]
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return None

    def recent_posts(self) -> list[dict]:
        """Read recent sent Buffer posts for the configured X channel."""
        channel = self._graphql(POSTS_CHANNEL, {"id": self.channel_id})["channel"]
        if (
            not channel
            or channel["id"] != self.channel_id
            or channel["service"] != "twitter"
        ):
            raise ValueError("Not an X channel")
        data = self._graphql(
            RECENT_POSTS,
            {
                "input": {
                    "organizationId": channel["organizationId"],
                    "filter": {"status": ["sent"], "channelIds": [self.channel_id]},
                    "sort": [{"field": "dueAt", "direction": "desc"}],
                }
            },
        )
        posts = []
        for edge in data["posts"]["edges"]:
            node = edge["node"]
            if node["channelId"] != self.channel_id or node["status"] != "sent":
                continue
            url = node["externalLink"]
            parsed = urlsplit(url or "")
            if parsed.scheme != "https" or parsed.netloc not in {
                "x.com",
                "twitter.com",
                "www.x.com",
                "www.twitter.com",
            }:
                url = None
            posts.append(
                {
                    "id": node["id"],
                    "text": node["text"],
                    "sent_at": node["sentAt"],
                    "url": url,
                }
            )
        return sorted(posts, key=lambda post: post["sent_at"] or "", reverse=True)

    def publish(self, text: str, expires: datetime) -> str:
        """Confirm the target, then submit Share Now once; acceptance is not delivery."""
        if not self.check_connection():
            return "buffer_blocked"
        if expires <= datetime.now(timezone.utc) + timedelta(seconds=15):
            return "expired"
        try:
            result = self._graphql(
                CREATE_POST,
                {
                    "input": {
                        "channelId": self.channel_id,
                        "text": text,
                        "schedulingType": "automatic",
                        "mode": "shareNow",
                    }
                },
            )["createPost"]
            if result["__typename"] != "PostActionSuccess":
                return (
                    "buffer_rejected" if result.get("message") else "buffer_uncertain"
                )
            post = result["post"]
            post_id = post["id"]
            if not isinstance(post_id, str) or not re.fullmatch(
                r"[A-Za-z0-9_-]{1,128}", post_id
            ):
                return "buffer_uncertain"
            LOGGER.info("Buffer Share Now receipt: %s", post_id)
            if post.get("status") == "sent":
                return "buffer_sent"
            if post.get("status") in {"error", "draft", "needs_approval"}:
                return "buffer_rejected"
            if post.get("status") in {"scheduled", "sending"}:
                return "buffer_accepted"
        except httpx.HTTPStatusError as exc:
            if 400 <= exc.response.status_code < 500:
                return "buffer_rejected"
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            pass
        return "buffer_uncertain"
