"""
Pydantic Schemas for Jargon Agent and Web Search Agent.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    """Represents a source document for a search result."""

    title: Optional[str] = Field(description="The title of the source document.")
    link: Optional[str] = Field(description="The URL of the source.")


class JargonDetail(BaseModel):
    """Details for a jargon term, including its definition."""

    term: str = Field(description="The jargon term found")
    definition: Optional[str] = Field(
        default=None, description="Definition if found in database"
    )


class JargonSearchDetail(BaseModel):
    """Details for a jargon term obtained from a web search."""

    term: str = Field(description="The jargon term found")
    definition: Optional[str] = Field(
        default=None, description="A summarized definition of the term."
    )
    sources: List[Source] = Field(
        default_factory=list, description="A list of source URLs and titles."
    )


class JargonQueryResult(BaseModel):
    """The complete result of the jargon query process."""

    detected_terms: List[JargonDetail] = Field(
        default=[], description="Terms found in database"
    )
    searched_terms: List[JargonSearchDetail] = Field(
        default=[], description="Terms searched on the web"
    )
    unknown_terms: List[JargonDetail] = Field(
        default=[], description="Terms not found or unclear"
    )


class WebSearchResult(BaseModel):
    """Result from the web search agent."""

    query: str = Field(description="The search query used")
    success: bool = Field(description="Whether the search was successful")
    results: str = Field(description="Formatted search results or error message")
    sources_found: int = Field(default=0, description="Number of sources found")


class FeatureArtifact(BaseModel):
    """Input model for the Jargon Agent."""

    feature_name: str = Field(description="Original feature name with potential jargon")
    feature_description: str = Field(description="Detailed functionality description")


class StandardizedFeature(BaseModel):
    """Output model from the Jargon Agent."""

    standardized_name: str = Field(description="Clear, jargon-free feature name")
    standardized_description: str = Field(description="Clean functionality description")
    jargon_result: JargonQueryResult = Field(
        description="The complete jargon query result"
    )
