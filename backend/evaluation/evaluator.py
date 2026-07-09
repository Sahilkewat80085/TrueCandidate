"""Evaluation script — runs all scenarios and measures system accuracy.

Outputs:
- Per-scenario results (correct/incorrect, time-to-identification, final confidence)
- Overall accuracy metrics
- Edge case analysis
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.app.config import AppConfig
from backend.app.connectors.mock_connector import MockMeetingConnector, list_scenarios
from backend.app.core.engine import IdentificationEngine


class EvaluationResult:
    def __init__(self, scenario_id: str, title: str, expected: str, difficulty: str):
        self.scenario_id = scenario_id
        self.title = title
        self.expected = expected
        self.difficulty = difficulty
        self.predicted: str | None = None
        self.final_confidence: float = 0.0
        self.correct: bool = False
        self.time_to_identification: float | None = None
        self.total_events: int = 0
        self.total_evidence: int = 0
        self.confidence_history: list[tuple[float, float]] = []  # (time, confidence)

    def __repr__(self):
        status = "[PASS]" if self.correct else "[FAIL]"
        tti = f"{self.time_to_identification:.0f}s" if self.time_to_identification else "N/A"
        return (
            f"{status} {self.scenario_id}: "
            f"conf={self.final_confidence:.0%}, "
            f"TTI={tti}, "
            f"events={self.total_events}, "
            f"evidence={self.total_evidence}"
        )


async def evaluate_scenario(
    scenario_path: str,
    scenario_data: dict,
    config: AppConfig,
) -> EvaluationResult:
    """Evaluate a single scenario."""
    result = EvaluationResult(
        scenario_id=scenario_data.get("scenario_id", ""),
        title=scenario_data.get("title", ""),
        expected=scenario_data.get("expected_candidate", ""),
        difficulty=scenario_data.get("difficulty", "medium"),
    )

    # Create connector (instant replay — no delays)
    connector = MockMeetingConnector(
        scenario_dir=str(Path(scenario_path).parent),
        speed=1000.0,  # As fast as possible
    )

    await connector.connect(scenario_data["scenario_id"])

    # Create engine
    engine = IdentificationEngine(config)
    engine.meeting_id = f"eval_{scenario_data['scenario_id']}"

    # Set calendar
    calendar = await connector.get_calendar_metadata()
    if calendar:
        engine.set_calendar(calendar)

    # Process all events
    await connector.start()
    identification_time = None

    async for event in connector.stream_events():
        prediction = engine.process_event(event)
        result.total_events += 1

        if prediction and prediction.current_candidate_id:
            result.predicted = prediction.current_candidate_id
            result.final_confidence = prediction.confidence

            result.confidence_history.append((event.timestamp, prediction.confidence))

            # Track time to first correct identification > 0.7
            if (
                prediction.current_candidate_id == result.expected
                and prediction.confidence >= 0.7
                and identification_time is None
            ):
                identification_time = event.timestamp

    result.time_to_identification = identification_time
    result.correct = result.predicted == result.expected
    result.total_evidence = len(engine.all_evidence)

    return result


async def run_evaluation():
    """Run all scenarios and print results."""
    scenario_dir = Path(__file__).parent.parent / "scenarios"
    config = AppConfig()
    config.llm.enabled = False  # Disable LLM for reproducible evaluation

    print("=" * 70)
    print("  TrueCandidate — Evaluation Report")
    print("=" * 70)
    print()

    results: list[EvaluationResult] = []

    for scenario_file in sorted(scenario_dir.glob("*.json")):
        data = json.loads(scenario_file.read_text(encoding="utf-8"))
        print(f"  Running: {data.get('title', scenario_file.stem)}...", end=" ", flush=True)

        try:
            result = await evaluate_scenario(str(scenario_file), data, config)
            results.append(result)
            print(result)
        except Exception as e:
            print(f"[ERROR] ERROR: {e}")

    print()
    print("=" * 70)
    print("  Summary")
    print("=" * 70)

    total = len(results)
    correct = sum(1 for r in results if r.correct)
    accuracy = correct / total if total > 0 else 0

    avg_confidence = sum(r.final_confidence for r in results) / total if total > 0 else 0
    tti_values = [r.time_to_identification for r in results if r.time_to_identification is not None]
    avg_tti = sum(tti_values) / len(tti_values) if tti_values else 0

    print(f"  Accuracy:           {correct}/{total} ({accuracy:.0%})")
    print(f"  Avg Final Conf:     {avg_confidence:.0%}")
    print(f"  Avg Time to ID:     {avg_tti:.0f}s")
    print(f"  Scenarios with TTI: {len(tti_values)}/{total}")
    print()

    # By difficulty
    print("  By Difficulty:")
    for diff in ["easy", "medium", "hard", "very_hard"]:
        diff_results = [r for r in results if r.difficulty == diff]
        if diff_results:
            diff_correct = sum(1 for r in diff_results if r.correct)
            print(f"    {diff:12s}: {diff_correct}/{len(diff_results)}")

    print()
    print("  Failed Scenarios:")
    failed = [r for r in results if not r.correct]
    if failed:
        for r in failed:
            print(f"    - {r.title}: predicted={r.predicted}, expected={r.expected}, conf={r.final_confidence:.0%}")
    else:
        print("    None! [SUCCESS]")

    print()
    print("=" * 70)

    return results


if __name__ == "__main__":
    asyncio.run(run_evaluation())
