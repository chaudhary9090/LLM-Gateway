"""Cost estimation calculations based on declarative model token pricing."""


def calculate_estimated_cost_usd(
    input_tokens: int,
    output_tokens: int,
    input_cost_per_1k: float,
    output_cost_per_1k: float,
) -> float:
    """Calculates estimated request cost in USD.

    Formula:
      (input_tokens / 1000.0) * input_cost_per_1k + (output_tokens / 1000.0) * output_cost_per_1k

    Note: This is an estimated cost for telemetry, budget tracking, and optimization.
    It does not represent an actual billed transaction.
    """
    input_cost = (max(0, input_tokens) / 1000.0) * max(0.0, input_cost_per_1k)
    output_cost = (max(0, output_tokens) / 1000.0) * max(0.0, output_cost_per_1k)
    total_cost = input_cost + output_cost
    return round(total_cost, 6)
