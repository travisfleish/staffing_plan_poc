from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from openai import OpenAI

# Configuration
DEFAULT_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
MAX_TOKENS = 4000

# OpenAI client
def _client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)

def embed_text_hybrid(text: str) -> List[float]:
    """Hybrid embedding approach combining full text with key section embeddings"""
    # Extract key sections that matter for staffing
    key_sections = {
        "scope": extract_scope_section(text),
        "business_units": extract_business_units(text), 
        "duration": extract_duration(text),
        "deliverables": extract_deliverables(text),
        "complexity": extract_complexity_indicators(text)
    }
    
    # Create weighted embedding
    embeddings = []
    weights = []
    
    # Full text (truncated) - 40% weight
    full_emb = embed_single_chunk(text[:8000])
    embeddings.append(full_emb)
    weights.append(0.4)
    
    # Key sections - 60% weight distributed equally
    section_weight = 0.6 / len([s for s in key_sections.values() if s])
    for section_name, section_text in key_sections.items():
        if section_text:
            section_emb = embed_single_chunk(section_text)
            embeddings.append(section_emb)
            weights.append(section_weight)
    
    # Weighted average
    return weighted_average_embeddings(embeddings, weights)

def embed_text_chunked(text: str, chunk_size: int = 4000, overlap: int = 500) -> List[float]:
    """Chunked embedding approach for long texts"""
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if len(chunk) >= chunk_size // 2:  # Only use substantial chunks
            chunks.append(chunk)
    
    # Embed each chunk
    chunk_embeddings = [embed_single_chunk(chunk) for chunk in chunks]
    
    # Use max pooling or weighted average based on chunk relevance
    return max_pool_embeddings(chunk_embeddings)

def embed_single_chunk(text: str) -> List[float]:
    """Embed a single text chunk"""
    cli = _client()
    if cli is None:
        import numpy as np
        rng = abs(hash(text)) % (10**6)
        return (np.ones(256) * (rng % 97) / 97.0).astype(float).tolist()
    
    resp = cli.embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding

def weighted_average_embeddings(embeddings: List[List[float]], weights: List[float]) -> List[float]:
    """Compute weighted average of multiple embeddings"""
    import numpy as np
    
    if not embeddings:
        return []
    
    # Normalize weights
    total_weight = sum(weights)
    if total_weight == 0:
        weights = [1.0 / len(weights)] * len(weights)
    else:
        weights = [w / total_weight for w in weights]
    
    # Weighted average
    weighted_emb = np.zeros(len(embeddings[0]))
    for emb, weight in zip(embeddings, weights):
        weighted_emb += np.array(emb) * weight
    
    return weighted_emb.tolist()

def max_pool_embeddings(embeddings: List[List[float]]) -> List[float]:
    """Use max pooling across chunk embeddings"""
    import numpy as np
    
    if not embeddings:
        return []
    
    # Convert to numpy array and take max across chunks
    emb_array = np.array(embeddings)
    return np.max(emb_array, axis=0).tolist()

def extract_scope_section(text: str) -> str:
    """Extract scope-related text using regex patterns"""
    import re
    
    # Look for scope indicators
    scope_patterns = [
        r'scope[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'project[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'overview[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'objectives?[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'goals?[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
    ]
    
    for pattern in scope_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    
    # Fallback: first few sentences
    sentences = text.split('.')[:3]
    return '. '.join(sentences).strip()

def extract_business_units(text: str) -> str:
    """Extract business unit mentions"""
    import re
    
    business_units = [
        'sponsorship strategy', 'tech', 'data', 'experience', 
        'client services', 'creative', 'operations', 'marketing',
        'strategy', 'design', 'development', 'analytics'
    ]
    
    found_units = []
    for unit in business_units:
        if re.search(rf'\b{re.escape(unit)}\b', text, re.IGNORECASE):
            found_units.append(unit)
    
    if found_units:
        return ', '.join(found_units)
    
    # Look for business unit patterns
    bu_patterns = [
        r'(?:business units?|departments?|teams?)[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'(?:creative|strategy|tech|data|operations)[\s\w]*',
    ]
    
    for pattern in bu_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0).strip()
    
    return ""

def extract_duration(text: str) -> str:
    """Extract duration information"""
    import re
    
    duration_patterns = [
        r'(\d+)\s*(?:month|week|day)s?',
        r'duration[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'timeline[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'project length[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
    ]
    
    for pattern in duration_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(0).strip()
    
    return ""

def extract_deliverables(text: str) -> str:
    """Extract deliverables information"""
    import re
    
    deliverable_patterns = [
        r'deliverables?[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'outputs?[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'final[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'create[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'develop[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
    ]
    
    for pattern in deliverable_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    
    return ""

def extract_complexity_indicators(text: str) -> str:
    """Extract complexity indicators"""
    import re
    
    complexity_words = [
        'complex', 'simple', 'basic', 'advanced', 'sophisticated',
        'integrated', 'multi-phase', 'multi-stage', 'end-to-end',
        'comprehensive', 'extensive', 'limited', 'focused'
    ]
    
    found_indicators = []
    for word in complexity_words:
        if re.search(rf'\b{re.escape(word)}\b', text, re.IGNORECASE):
            found_indicators.append(word)
    
    if found_indicators:
        return ', '.join(found_indicators)
    
    # Look for complexity patterns
    complexity_patterns = [
        r'complexity[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'level[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
        r'scope[:\s]+(.*?)(?=\n\n|\n[A-Z]|$)',
    ]
    
    for pattern in complexity_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    
    return ""

def embed_text(text: str) -> List[float]:
    """Main embedding function - uses hybrid approach by default"""
    return embed_text_hybrid(text)

def analyze_sow_text(text: str) -> Dict[str, Any]:
    """Analyze SOW text and extract structured information"""
    cli = _client()
    if cli is None:
        return {
            "complexity_level": "medium",
            "duration_months": 4,
            "workstream_count": 2,
            "estimated_total_hours": 800,
            "key_deliverables": ["Strategy document", "Creative assets"]
        }
    
    prompt = (
        "You are a staffing planner. Read the SOW text and return JSON with: "
        "complexity_level (low|medium|high), duration_months (number), workstream_count (number), "
        "estimated_total_hours (number - estimate total staffing hours needed), key_deliverables (list of strings). "
        "Provide realistic estimates based on the scope and duration described. "
        "Ensure estimated_total_hours and duration_months are numeric values."
    )
    
    try:
        resp = cli.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text[:12000]}
            ],
            response_format={"type": "json_object"},
        )
        
        import json
        result = json.loads(resp.choices[0].message.content)
        
        # Validate and ensure numeric values
        if not isinstance(result.get("estimated_total_hours"), (int, float)) or result.get("estimated_total_hours", 0) <= 0:
            result["estimated_total_hours"] = 800
        if not isinstance(result.get("duration_months"), (int, float)) or result.get("duration_months", 0) <= 0:
            result["duration_months"] = 4
            
        return result
        
    except Exception as e:
        print(f"Error analyzing SOW text: {e}")
        return {
            "complexity_level": "medium",
            "duration_months": 4,
            "workstream_count": 2,
            "estimated_total_hours": 800,
            "key_deliverables": ["Strategy document", "Creative assets"]
        }

def test_embedding_improvement():
    """Test the new hybrid embedding approach"""
    sample_text = """
    Project: Delta Airlines Sponsorship Strategy
    Duration: 12 months
    Business Units: Creative, Strategy, Client Services, Operations
    
    Scope: Comprehensive year-long retainer for Delta Airlines sponsorship strategy
    and creative execution. This includes brand positioning, campaign development,
    media planning, and ongoing optimization.
    
    Deliverables: Brand strategy document, creative campaign concepts, media plan,
    performance reports, and ongoing consultation.
    
    Complexity: Multi-phase integrated campaign requiring cross-functional collaboration
    between creative, strategy, and client services teams.
    """
    
    print("Testing hybrid embedding approach...")
    
    # Test hybrid embedding
    hybrid_emb = embed_text_hybrid(sample_text)
    print(f"Hybrid embedding length: {len(hybrid_emb)}")
    print(f"Hybrid embedding sample: {hybrid_emb[:5]}")
    
    # Test chunked embedding
    chunked_emb = embed_text_chunked(sample_text)
    print(f"Chunked embedding length: {len(chunked_emb)}")
    print(f"Chunked embedding sample: {chunked_emb[:5]}")
    
    # Test key section extraction
    print("\nKey sections extracted:")
    print(f"Scope: {extract_scope_section(sample_text)}")
    print(f"Business Units: {extract_business_units(sample_text)}")
    print(f"Duration: {extract_duration(sample_text)}")
    print(f"Deliverables: {extract_deliverables(sample_text)}")
    print(f"Complexity: {extract_complexity_indicators(sample_text)}")
    
    print("\nEmbedding test completed successfully!")

if __name__ == "__main__":
    test_embedding_improvement()
