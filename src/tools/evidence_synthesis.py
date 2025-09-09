"""Evidence synthesis for combining multiple probe results into coherent answers."""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


def synthesize_evidence(query: str, evidence_packs: List[Dict[str, Any]]) -> str:
    """
    Synthesize multiple evidence packs into a structured answer.
    
    Args:
        query: Original user query
        evidence_packs: List of evidence packs from probes
        
    Returns:
        Formatted answer with citations
    """
    if not evidence_packs:
        return "No evidence found to answer your query."
    
    # Deduplicate and rank evidence
    seen_content = set()
    unique_evidence = []
    path_to_evidence = {}
    
    for pack in evidence_packs:
        probe_type = pack.get("type", "search")
        for item in pack.get("doc_pack", []):
            path = item.get("path", "")
            excerpt = item.get("excerpt", "")
            score = item.get("score", 0.0)
            
            # Create content key for deduplication
            content_key = (path, excerpt[:100] if excerpt else "")
            if content_key not in seen_content:
                seen_content.add(content_key)
                
                # Group evidence by path
                if path not in path_to_evidence:
                    path_to_evidence[path] = {
                        "path": path,
                        "excerpts": [],
                        "max_score": score,
                        "probe_types": set()
                    }
                
                path_to_evidence[path]["excerpts"].append({
                    "text": excerpt,
                    "start_line": item.get("start_line"),
                    "end_line": item.get("end_line"),
                    "score": score
                })
                path_to_evidence[path]["max_score"] = max(path_to_evidence[path]["max_score"], score)
                path_to_evidence[path]["probe_types"].add(probe_type)
    
    # Sort by relevance (score and probe diversity)
    ranked_paths = sorted(
        path_to_evidence.items(),
        key=lambda x: (x[1]["max_score"], len(x[1]["probe_types"])),
        reverse=True
    )
    
    # Build structured answer
    answer_parts = [f"## Answer\n\nBased on the codebase analysis for: \"{query}\"\n"]
    
    # Categorize evidence by type
    categories = {
        "Core Implementation": [],
        "Configuration": [],
        "Tests": [],
        "Documentation": [],
        "Supporting Files": []
    }
    
    for path, evidence in ranked_paths[:15]:  # Top 15 files
        # Categorize based on path patterns
        if any(pat in path.lower() for pat in ["test", "spec", "_test.", ".test."]):
            category = "Tests"
        elif any(pat in path.lower() for pat in ["config", "settings", ".env", ".yaml", ".yml", ".json"]):
            category = "Configuration"
        elif any(pat in path.lower() for pat in ["readme", "docs", ".md", "documentation"]):
            category = "Documentation"
        elif any(pat in path.lower() for pat in ["src/", "lib/", "core/", "main", "index", "app"]):
            category = "Core Implementation"
        else:
            category = "Supporting Files"
        
        categories[category].append((path, evidence))
    
    # Generate answer sections
    for category, items in categories.items():
        if items:
            answer_parts.append(f"\n### {category}\n")
            
            for path, evidence in items[:5]:  # Limit to 5 per category
                # Add file reference
                excerpts = evidence["excerpts"]
                if excerpts:
                    # Get best excerpt
                    best_excerpt = max(excerpts, key=lambda x: x.get("score", 0))
                    lines_info = ""
                    if best_excerpt.get("start_line"):
                        lines_info = f":{best_excerpt['start_line']}"
                        if best_excerpt.get("end_line"):
                            lines_info += f"-{best_excerpt['end_line']}"
                    
                    answer_parts.append(f"- **{path}{lines_info}**")
                    
                    # Add excerpt if meaningful
                    text = best_excerpt.get("text", "").strip()
                    if text and len(text) > 20:
                        # Format code excerpt
                        lines = text.split("\n")[:8]  # Limit to 8 lines
                        if lines:
                            answer_parts.append("  ```")
                            for line in lines:
                                if line.strip():  # Only non-empty lines
                                    answer_parts.append(f"  {line[:120]}")  # Truncate long lines
                            if len(lines) < len(text.split("\n")):
                                answer_parts.append("  ...")
                            answer_parts.append("  ```")
    
    # Add evidence summary
    answer_parts.append(f"\n## Evidence Summary\n")
    answer_parts.append(f"- Analyzed {len(evidence_packs)} probe results")
    answer_parts.append(f"- Found relevant code in {len(path_to_evidence)} unique files")
    answer_parts.append(f"- Top matches from {len([p for p in ranked_paths if p[1]['max_score'] > 0.5])} high-confidence sources")
    
    # Suggest follow-up if needed
    if len(path_to_evidence) < 3:
        answer_parts.append("\n## Note\n")
        answer_parts.append("Limited evidence found. Consider:")
        answer_parts.append("- Refining your query with more specific terms")
        answer_parts.append("- Checking if the repository has been properly indexed")
        answer_parts.append("- Verifying that the feature/component exists in the codebase")
    
    return "\n".join(answer_parts)


def rank_evidence_by_relevance(
    evidence_items: List[Dict[str, Any]], 
    query_terms: List[str]
) -> List[Dict[str, Any]]:
    """
    Rank evidence items by relevance to query terms.
    
    Args:
        evidence_items: List of evidence items with path, excerpt, score
        query_terms: List of query terms to match
        
    Returns:
        Sorted list of evidence items
    """
    for item in evidence_items:
        relevance_score = item.get("score", 0.0)
        
        # Boost score based on query term matches
        text = (item.get("excerpt", "") + " " + item.get("path", "")).lower()
        for term in query_terms:
            if term.lower() in text:
                relevance_score += 0.1
        
        # Boost for specific file patterns
        path = item.get("path", "").lower()
        if any(pat in path for pat in ["main", "index", "app", "core"]):
            relevance_score += 0.05
        
        item["relevance_score"] = relevance_score
    
    return sorted(evidence_items, key=lambda x: x.get("relevance_score", 0), reverse=True)