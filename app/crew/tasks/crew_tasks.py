"""
CrewAI Tasks - Sequential RAG Pipeline
Tasks define what agents should accomplish
"""
from typing import Dict, Any, List
from crewai import Task

from app.crew.agents.retriever_agent import create_retriever_agent
from app.crew.agents.context_agent import create_context_agent
from app.crew.agents.analyst_agent import create_analyst_agent
from app.crew.agents.compliance_agent import create_compliance_agent
from app.crew.agents.answer_agent import create_answer_agent


def create_retrieval_task(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    agent=None
) -> Task:
    """
    Task 1: Process retrieved vector search results.
    
    Args:
        query: User's original query
        retrieved_chunks: Results from Pinecone query
        agent: RetrieverAgent instance (optional)
    """
    if agent is None:
        agent = create_retriever_agent()
    
    description = f"""
    Process the vector search results for the query: "{query}"
    
    Retrieved chunks have been fetched from the vector database. Your job is to:
    1. Review the {len(retrieved_chunks)} retrieved chunks
    2. Verify relevance scores (must be >= 0.7)
    3. Extract and organize metadata (email_id, subject, sender, date, thread_id)
    4. Prepare the chunks for context reconstruction
    5. Note any missing or incomplete metadata
    
    Retrieved Chunks:
    {retrieved_chunks}
    
    Output Format:
    Provide a structured JSON with:
    - query: the original query
    - num_chunks: count of chunks
    - chunks: list of chunks with metadata
    - emails_found: unique email IDs
    - threads_found: unique thread IDs
    - date_range: earliest and latest email dates
    - top_senders: most common senders
    """
    
    return Task(
        description=description,
        agent=agent,
        expected_output=(
            "JSON object containing organized retrieved chunks with complete metadata, "
            "ready for context reconstruction. Include summary statistics about the "
            "retrieved emails (count, date range, senders, threads)."
        )
    )


def create_context_task(agent=None) -> Task:
    """
    Task 2: Reconstruct email context from chunks.
    
    Args:
        agent: ContextAgent instance (optional)
    """
    if agent is None:
        agent = create_context_agent()
    
    description = """
    Reconstruct full email context from the retrieved chunks.
    
    You will receive organized chunks from the RetrieverAgent. Your job is to:
    1. Group chunks by email_id to reconstruct full emails
    2. Group emails by thread_id to reconstruct conversations
    3. Sort emails within each thread chronologically by sent_at timestamp
    4. Build a narrative of each conversation showing progression over time
    5. Preserve all metadata: sender, recipient, subject, date
    6. Identify the context and relationships between emails in threads
    
    Output Format:
    Provide structured JSON with:
    - threads: list of email threads
      - thread_id: thread identifier
      - emails: list of emails in chronological order
        - email_id: unique email ID
        - subject: email subject
        - sender: who sent it
        - sent_at: when it was sent
        - content: reconstructed full content from chunks
        - recipients: who received it
    - standalone_emails: emails not part of any thread
    - conversation_summary: high-level overview of what these emails discuss
    """
    
    return Task(
        description=description,
        agent=agent,
        expected_output=(
            "JSON object with reconstructed email threads in chronological order, "
            "showing the full conversation flow. Each email should have complete "
            "content assembled from chunks and all metadata preserved."
        ),
        context=[]  # Will be populated with previous task output
    )


def create_analysis_task(user_query: str, agent=None) -> Task:
    """
    Task 3: Analyze emails to answer the user's question.
    
    Args:
        user_query: The user's original question
        agent: AnalystAgent instance (optional)
    """
    if agent is None:
        agent = create_analyst_agent()
    
    description = f"""
    Analyze the reconstructed email conversations to answer the user's query.
    
    User Query: "{user_query}"
    
    You will receive reconstructed email threads from the ContextAgent. Your job is to:
    1. Read and understand all email conversations
    2. Identify information relevant to the user's query
    3. Extract key insights:
       - Decisions made (who decided what, when)
       - Action items and owners
       - Agreements and disagreements
       - Deadlines and timelines
       - Risks and concerns raised
       - Open questions
    4. Note conflicting information if present
    5. Provide evidence by citing specific emails
    
    Analysis Guidelines:
    - ONLY use information from the provided emails
    - Cite specific emails for every claim (format: Email from [Sender] on [Date])
    - If information is not in the emails, explicitly state that
    - Note uncertainty or ambiguity when present
    - Identify if the question cannot be fully answered from available emails
    
    Output Format:
    Provide JSON with:
    - answer_possible: true/false (can the query be answered from these emails?)
    - main_findings: list of key insights with email citations
    - decisions: list of decisions with who/what/when
    - action_items: list of actions with owners
    - timeline: important dates mentioned
    - risks: concerns or blockers identified
    - missing_information: what's needed but not found in emails
    - email_citations: list of emails referenced with IDs and subjects
    """
    
    return Task(
        description=description,
        agent=agent,
        expected_output=(
            "JSON object with detailed analysis of emails, answering the user's query "
            "with specific citations. Clearly indicate if the query can be fully answered "
            "or if information is missing. All claims must be supported by email evidence."
        ),
        context=[]  # Will be populated with previous task output
    )


def create_compliance_task(agent=None) -> Task:
    """
    Task 4: Review analysis for compliance and redact PII.
    
    Args:
        agent: ComplianceAgent instance (optional)
    """
    if agent is None:
        agent = create_compliance_agent()
    
    description = """
    Review the analysis for compliance and security concerns.
    
    You will receive the AnalystAgent's findings. Your job is to:
    1. Scan all content for PII:
       - Social Security Numbers (XXX-XX-XXXX)
       - Credit card numbers (16 digits)
       - Passport numbers
       - Driver's license numbers
       - Full dates of birth with names
    2. Scan for confidential information:
       - Financial data (revenue, profit numbers)
       - Unreleased product information
       - Trade secrets
       - Legal matter details
    3. Apply redactions if PII_REDACTION_ENABLED:
       - Replace PII with [REDACTED-TYPE]
       - Example: "SSN 123-45-6789" → "[REDACTED-SSN]"
    4. Flag sensitive content that needs special handling
    5. Verify all claims are traceable to source emails
    6. Document compliance actions taken
    
    Output Format:
    Provide JSON with:
    - pii_found: true/false
    - pii_types: list of PII types detected (if any)
    - pii_redacted: true/false (whether redactions were applied)
    - redaction_count: number of redactions made
    - sensitive_flags: list of sensitivity concerns
    - compliance_notes: what actions were taken and why
    - traceability_verified: true/false (all claims have source emails)
    - safe_content: the analysis with any necessary redactions applied
    """
    
    return Task(
        description=description,
        agent=agent,
        expected_output=(
            "JSON object with compliance review results, including any PII/sensitive "
            "content flags, redactions applied, and the safe version of the analysis "
            "that can be shown to the user. Verify traceability of all claims."
        ),
        context=[]  # Will be populated with previous task output
    )


def create_answer_task(user_query: str, agent=None) -> Task:
    """
    Task 5: Generate final user-facing answer.
    
    Args:
        user_query: The user's original question
        agent: AnswerAgent instance (optional)
    """
    if agent is None:
        agent = create_answer_agent()
    
    description = f"""
    Generate the final answer for the user based on compliance-reviewed analysis.
    
    User Query: "{user_query}"
    
    You will receive compliance-reviewed analysis from the ComplianceAgent. Your job is to:
    1. Synthesize the analysis into a clear, coherent answer
    2. Structure the answer appropriately:
       - Start with a direct answer to the question
       - Follow with supporting details
       - Include relevant context
       - End with any caveats or limitations
    3. Include citations for all claims:
       - Format: "According to Email from [Sender] on [Date] with subject '[Subject]'..."
       - List all source emails at the end
    4. If the query cannot be fully answered:
       - State this clearly upfront
       - Explain what information is missing
       - Provide what partial answer is possible
       - Suggest what additional emails might help
    5. Use professional, clear language
    6. Format with markdown for readability (headings, bullets)
    
    CRITICAL RULES:
    - NEVER add information not in the emails
    - NEVER speculate or make assumptions
    - NEVER fill in gaps with outside knowledge
    - If unsure, say "Based on the available emails, I cannot determine..."
    - If conflicting information exists, present both sides
    
    Output Format:
    Provide JSON with:
    - answer: the complete user-facing answer (markdown formatted)
    - answer_complete: true/false (query fully answered?)
    - confidence: high/medium/low
    - sources: list of email sources cited
      - email_id, subject, sender, date, relevance
    - limitations: any caveats or missing information
    - follow_up_suggestions: what additional searches might help
    """
    
    return Task(
        description=description,
        agent=agent,
        expected_output=(
            "JSON object with the final answer to the user's query, properly formatted "
            "with markdown, fully cited with source emails, and clearly indicating if "
            "the answer is complete or if information is missing. The answer must be "
            "grounded in email evidence and never hallucinate."
        ),
        context=[]  # Will be populated with previous task output
    )


# Export
__all__ = [
    "create_retrieval_task",
    "create_context_task",
    "create_analysis_task",
    "create_compliance_task",
    "create_answer_task"
]
