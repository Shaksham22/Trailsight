"""Credential-free deterministic V2 AI eval using an independent mocked execution path."""

from trailsight_v2.ai.evals import (
    execute_non_live_scenario,
    load_eval_suite,
    validate_eval_observation,
)


def main() -> None:
    suite = load_eval_suite()
    results = []
    for scenario in suite.scenarios:
        observation = execute_non_live_scenario(scenario)
        results.append(validate_eval_observation(scenario, observation))

    failed = [result for result in results if not result.passed]
    if failed:
        raise SystemExit(f"non-live deterministic eval failed: {failed}")
    print(f"non_live_eval_scenarios={len(results)} status=PASS")


if __name__ == "__main__":
    main()
