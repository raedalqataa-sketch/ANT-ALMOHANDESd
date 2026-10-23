"""Deterministic CP-SAT selection of distinct, already-validated plans.

This solves the *portfolio selection* problem after geometry and program
validation. It does not prove optimal room allocation or code compliance.
"""
from ortools.sat.python import cp_model


def choose_distinct_subset(candidate_count, incompatible_pairs, *, limit=3):
    """Lexicographically maximize number of alternatives, then prefer score rank.

    Candidates are indexed in ascending validated heuristic score order.
    Conflicts identify alternatives that are not materially different.
    """
    if candidate_count < 0 or limit < 0:
        raise ValueError("candidate_count and limit must be nonnegative")
    if candidate_count == 0 or limit == 0:
        return [], {"status": "OPTIMAL", "optimality_proven": True,
                    "eligible_count": candidate_count, "selected_count": 0}
    if candidate_count > 64:
        raise ValueError("CP-SAT portfolio is limited to 64 validated candidates")
    model = cp_model.CpModel()
    picked = [model.new_bool_var(f"plan_{index}") for index in range(candidate_count)]
    model.add(sum(picked) <= limit)
    for left, right in incompatible_pairs:
        if not (0 <= left < right < candidate_count):
            raise ValueError("incompatible pair must be unique ordered valid indices")
        model.add(picked[left] + picked[right] <= 1)
    # The cardinality bonus is greater than any possible rank penalty for
    # up to 'limit' members. Thus a third valid alternative is never traded
    # for a marginally better-scoring pair.
    cardinality_bonus = candidate_count * min(limit, candidate_count) + 1
    model.maximize(sum((cardinality_bonus - i) * var for i, var in enumerate(picked)))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError(f"CP-SAT portfolio did not produce a feasible result ({status})")
    indices = [i for i, selected in enumerate(picked) if solver.value(selected)]
    return indices, {
        "status": solver.status_name(status),
        "optimality_proven": status == cp_model.OPTIMAL,
        "eligible_count": candidate_count,
        "selected_count": len(indices),
        "method": "cardinality-first CP-SAT independent set over measured pairwise plan diversity; score rank tie-break",
        "allocation_optimality_proven": False,
    }
