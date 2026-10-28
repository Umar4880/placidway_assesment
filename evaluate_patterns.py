"""
Evaluation and Benchmark Runner for PydanticAI Clinical Agent.
Runs the 8 mandatory test cases and scores grounding, citations, latency, and guardrails.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from benchmarks.evaluate_patterns import PydanticAIBenchmarkRunner


if __name__ == "__main__":
    runner = PydanticAIBenchmarkRunner()
    try:
        asyncio.run(runner.run_full_benchmark())
    finally:
        runner.close()
