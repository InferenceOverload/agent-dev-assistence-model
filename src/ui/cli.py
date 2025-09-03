#!/usr/bin/env python3
"""CLI for the Orchestrator Agent - runs ingest, decide, index, ask pipeline."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from src.agents.orchestrator import OrchestratorAgent


def run_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    """Run the orchestrator pipeline based on subcommand.
    
    Args:
        args: Parsed command line arguments
        
    Returns:
        Result dictionary to output as JSON
        
    Raises:
        AssertionError: If required steps haven't been run
        Exception: For other pipeline errors
    """
    orchestrator = OrchestratorAgent(root=args.root, session_id=args.session)
    
    if args.command == "ingest":
        return orchestrator.ingest()
    
    elif args.command == "decide":
        # Ensure ingest has been called; if not, call it
        if orchestrator.code_map is None:
            orchestrator.ingest()
        return orchestrator.size_and_decide()
    
    elif args.command == "index":
        # Call ingest+decide first if needed
        if orchestrator.code_map is None:
            orchestrator.ingest()
        if orchestrator.decision is None:
            orchestrator.size_and_decide()
        return orchestrator.index()
    
    elif args.command == "ask":
        # Ensure full pipeline has been run
        if orchestrator.code_map is None:
            orchestrator.ingest()
        if orchestrator.decision is None:
            orchestrator.size_and_decide()
        # Check if index exists for this session
        retriever = orchestrator.storage_factory.session_store().get_retriever(args.session)
        if retriever is None:
            orchestrator.index()
        return orchestrator.ask(args.query, k=args.k, write_docs=args.write_docs)
    
    elif args.command == "all":
        # Run ingest -> decide -> index
        ingest_result = orchestrator.ingest()
        decide_result = orchestrator.size_and_decide()
        index_result = orchestrator.index()
        
        result = {
            "ingest": ingest_result,
            "decide": decide_result,
            "index": index_result
        }
        
        # If query passed, also ask
        if args.query:
            ask_result = orchestrator.ask(args.query, k=args.k, write_docs=args.write_docs)
            result["ask"] = ask_result
        
        return result
    
    else:
        raise ValueError(f"Unknown command: {args.command}")


def main() -> None:
    """Main CLI entry point."""
    # Create a parent parser with common arguments
    common_parser = argparse.ArgumentParser(add_help=False)
    common_parser.add_argument("--root", type=str, default=".", help="Repository root path (default: .)")
    common_parser.add_argument("--session", type=str, default="default", help="Session ID (default: default)")
    common_parser.add_argument("--query", type=str, help="Query text (for ask/all commands)")
    common_parser.add_argument("--k", type=int, default=12, help="Number of results to retrieve (default: 12)")
    common_parser.add_argument("--write-docs", action="store_true", help="Write documentation files")
    
    # Main parser
    parser = argparse.ArgumentParser(
        prog="adk-orch",
        description="Orchestrator CLI - runs ingest→decide→index→ask pipeline",
        parents=[common_parser]
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # ingest subcommand
    ingest_parser = subparsers.add_parser("ingest", help="Ingest repository and create code map",
                                         parents=[common_parser])
    
    # decide subcommand  
    decide_parser = subparsers.add_parser("decide", help="Size repository and make vectorization decision",
                                         parents=[common_parser])
    
    # index subcommand
    index_parser = subparsers.add_parser("index", help="Index chunks and build retriever",
                                        parents=[common_parser])
    
    # ask subcommand
    ask_parser = subparsers.add_parser("ask", help="Ask a query using RAG",
                                      parents=[common_parser])
    
    # all subcommand
    all_parser = subparsers.add_parser("all", help="Run full pipeline (ingest→decide→index, optionally ask)",
                                      parents=[common_parser])
    
    # Parse arguments
    args = parser.parse_args()
    
    # Validate required arguments
    if args.command is None:
        parser.print_help()
        sys.exit(1)
    
    # For ask command, ensure query is provided
    if args.command == "ask":
        if not args.query:
            print("Error: --query is required for ask command", file=sys.stderr)
            sys.exit(1)
    
    # Validate root path exists
    if not Path(args.root).exists():
        print(f"Error: Root path '{args.root}' does not exist", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Run the pipeline
        result = run_pipeline(args)
        
        # Output compact JSON to stdout
        print(json.dumps(result, separators=(',', ':')))
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()