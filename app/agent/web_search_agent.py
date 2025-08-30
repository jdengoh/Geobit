"""
Web Search Agent with Parallel Web Search Tool.
"""

import asyncio
import logging
import os
import re
from typing import List

import aiohttp
from agents import Agent, RunContextWrapper, function_tool
from openai import AsyncOpenAI
from dotenv import load_dotenv
from app.agent.schemas.evidence import Evidence, Finding, RetrievalNeed
from app.agent.schemas.jargons import JargonSearchDetail, Source

load_dotenv()

logger = logging.getLogger(__name__)

# Helper functions for data processing
def _format_serper_results(response_data: dict, query: str) -> str:
    """Formats Google Serper API response into a readable string."""
    organic_results = response_data.get("organic", [])
    if not organic_results:
        return f"No results found for: {query}"
    results = []
    for i, result in enumerate(organic_results[:3], 1):
        title = result.get("title", "No title")
        snippet = result.get("snippet", "No description")
        link = result.get("link", "")
        formatted_result = (
            f"Result {i}:\nTitle: {title}\nSnippet: {snippet}\nLink: {link}"
        )
        results.append(formatted_result)
    return "\n\n".join(results)


def _extract_sources(raw_results: str) -> List[Source]:
    """Parses a string of formatted search results to extract sources."""
    sources = []
    pattern = re.compile(r"Title: (.+?)\n.*?Link: (.+)", re.DOTALL)
    for match in pattern.finditer(raw_results):
        title, link = match.groups()
        sources.append(Source(title=title.strip(), link=link.strip()))
    return sources


async def _get_llm_summary(client: AsyncOpenAI, term: str, raw_results: str) -> str:
    """Makes a direct LLM call to summarize search results."""
    prompt = f"""
    Please provide a concise, single-paragraph summary of the following search results for the term "{term}".
    Focus on the definition and purpose.
    Search Results:
    {raw_results}
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.info(f"❌ LLM summarization failed for {term}: {e}")
        return "Definition not available."


async def _single_request(
    client: AsyncOpenAI, query: str, max_retries: int, retry_delay: int
):
    """Handles a single Serper API search and summarization request."""
    api_key = os.getenv("SERPER_API_KEY")
    if not api_key:
        logger.warning("❌ SERPER_API_KEY not set")
        raise Exception("SERPER_API_KEY not set")

    payload = {"q": f"{query} in software development", "num": 3}
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    raw_results = ""

    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://google.serper.dev/search", json=payload, headers=headers
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        raw_results = _format_serper_results(data, query)
                        break
                    elif response.status in [429, 500, 502, 503, 504]:
                        await asyncio.sleep(retry_delay)
        except Exception:
            await asyncio.sleep(retry_delay)

    logger.info(f"🔍 Search results for '{query}' obtained")
    if raw_results and not raw_results.startswith("❌"):
        logger.info(f"📝 Summarizing results for '{query}'")
        summary = await _get_llm_summary(client, query, raw_results)
        # sources = _extract_sources(raw_results)
        logger.info(f"✅ Summary for '{query}': {summary[:60]}...")
        # return JargonSearchDetail(term=query, definition=summary, sources=sources)
        return JargonSearchDetail(term=query, definition=summary)
    else:
        return JargonSearchDetail(term=query, definition=None)


@function_tool
async def multi_serper_search(
    ctx: RunContextWrapper,  # Added RunContextWrapper to access the shared context
    terms: List[str],
    max_retries: int = 3,
    retry_delay: int = 1,
) -> List[JargonSearchDetail]:
    """
    Performs parallel Serper API searches and summarizes them using a manual LLM call.
    Returns a list of JargonSearchDetail objects.
    """
    logger.info(f"🌐 Starting parallel searches for {len(terms)} terms.")

    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    tasks = [
        _single_request(openai_client, term, max_retries, retry_delay) for term in terms
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed_results = []
    for res in results:
        if isinstance(res, JargonSearchDetail):
            processed_results.append(res)
        else:
            logger.info(f"❌ Failed to process term, skipping: {res}")

    # Append the processed results to the context
    if ctx and ctx.context and ctx.context.jargon_translation:
        ctx.context.jargon_translation.searched_terms.extend(processed_results)
        searched_terms_set = {
            result.term for result in processed_results if result.definition is not None
        }
        ctx.context.jargon_translation.unknown_terms = [
            term_detail
            for term_detail in ctx.context.jargon_translation.unknown_terms
            if term_detail.term not in searched_terms_set
        ]

    logger.info(
        f"✅ Updated context: {ctx.context.jargon_translation.model_dump_json()}"
    )

    return processed_results


def web_search_agent_prompt(context_wrapper, agent) -> str:
    """Instructions for the web search agent."""
    return """
You are a Web Search Agent specialized in finding and processing definitions for technical terms.

Your sole task is to identify individual jargon terms from the provided input and use the `multi_serper_search` tool to get their definitions.

**Instructions:**
- Identify and list all distinct jargon terms.
- **Do not** combine multiple terms into a single string.
- The `multi_serper_search` tool expects a list of strings (e.g., `terms=["term1", "term2"]`).

**Example:**
If the user's request is "Find the definitions for CustomAPI and XRAY", your tool call must be:
`multi_serper_search(terms=["CustomAPI", "XRAY"])`

Once you receive the results from the tool, they will be in the form of a list of `JargonSearchDetail` objects, each containing:
- `term`: The jargon term.
- `definition`: A summarized definition of the term.

IMMEDIATELY RETURN this list of `JargonSearchDetail` objects as your final output, no need to add any extra text or commentary.

"""

def create_web_search_agent():
    """Create the Web Search Agent with parallel search and summarization capability."""
    return Agent(
        name="Web Search Agent",
        instructions=web_search_agent_prompt,
        tools=[multi_serper_search],
        output_type=List[JargonSearchDetail],
        model="gpt-5-nano",
    )
