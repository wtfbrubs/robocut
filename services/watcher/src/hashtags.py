import os
import re
import asyncio
from clipbot_shared.logger import get_logger

log = get_logger("hashtags")

_RULES: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"\birl\b", re.I), ["#IRL", "#vlog"]),
    (re.compile(r"\btravel|viagem|viajando\b", re.I), ["#travel", "#viagem"]),
    (re.compile(r"\bnoite|night|balada|club\b", re.I), ["#nightlife", "#noite"]),
    (re.compile(r"\bcomer|comida|food|restaurante\b", re.I), ["#food", "#comida"]),
    (re.compile(r"\bjogo|game|gaming|gameplay\b", re.I), ["#gaming", "#gamer"]),
    (re.compile(r"\bmusic|musica|show|concert\b", re.I), ["#music", "#show"]),
    (re.compile(r"\bfitness|academia|gym|treino\b", re.I), ["#fitness", "#gym"]),
    (re.compile(r"\bpraia|beach|mar|surf\b", re.I), ["#beach", "#praia"]),
    (re.compile(r"\bfortnite\b", re.I), ["#fortnite"]),
    (re.compile(r"\bvalor+ant\b", re.I), ["#valorant"]),
    (re.compile(r"\bcs2?|counter.?strike\b", re.I), ["#cs2"]),
    (re.compile(r"\bfifa|fut+ebol|soccer\b", re.I), ["#fifa", "#futebol"]),
    (re.compile(r"\bjust chatting|papo|bate.?papo\b", re.I), ["#justchatting", "#live"]),
]


def _rule_based(title: str, category: str, base_hashtags: list[str]) -> list[str]:
    text = f"{title} {category}"
    extra: list[str] = []
    for pattern, tags in _RULES:
        if pattern.search(text):
            extra.extend(tags)
    seen: set[str] = set()
    result: list[str] = []
    for tag in base_hashtags + extra:
        key = tag.lower()
        if key not in seen:
            seen.add(key)
            result.append(tag)
    return result[:30]


async def _llm_hashtags(title: str, category: str, base_hashtags: list[str], platform: str) -> list[str]:
    from openai import AsyncOpenAI

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY not set")

    client = AsyncOpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )

    base_str = " ".join(base_hashtags)
    prompt = (
        f"Generate 8 TikTok hashtags for a live stream clip.\n"
        f"Platform: {platform}\n"
        f"Title: {title}\n"
        f"Category: {category}\n"
        f"Base hashtags: {base_str}\n\n"
        f"Rules:\n"
        f"- Return ONLY hashtags, one per line, starting with #\n"
        f"- Mix Portuguese and English based on the content language\n"
        f"- Include the base hashtags plus relevant ones for the title/category\n"
        f"- No explanations, no numbering, just hashtags"
    )

    resp = await asyncio.wait_for(
        client.chat.completions.create(
            model="meta/llama-3.1-8b-instruct",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100,
            temperature=0.3,
        ),
        timeout=10,
    )

    text = resp.choices[0].message.content or ""
    tags = [t.strip() for t in text.splitlines() if t.strip().startswith("#")]
    if not tags:
        raise ValueError("LLM returned no hashtags")
    return tags[:30]


async def generate_hashtags(
    title: str,
    category: str,
    base_hashtags: list[str],
    platform: str,
) -> list[str]:
    try:
        return await _llm_hashtags(title, category, base_hashtags, platform)
    except Exception as exc:
        log.warning("llm_hashtags_failed_using_rules", error=str(exc))
        return _rule_based(title, category, base_hashtags)
