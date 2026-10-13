DEFAULT_SOURCE_GROUP_URLS = [
    "https://t.me/promotom",
    "https://t.me/fumotom",
    "https://t.me/promochina",
    "https://t.me/promotop",
    "https://t.me/peperaiohardware",
    "https://t.me/achadinhomily",
    "https://t.me/achadinhossdamily1",
]


def approved_source(chat: str) -> str:
    """Return canonical catalog URL; reject user-supplied sources."""
    name = (
        chat.strip()
        .removeprefix("https://t.me/")
        .removeprefix("http://t.me/")
        .removeprefix("@")
        .rstrip("/")
        .lower()
    )
    for url in DEFAULT_SOURCE_GROUP_URLS:
        if name == url.rsplit("/", 1)[-1].lower():
            return url
    raise ValueError("Select a source group from the platform catalog")
