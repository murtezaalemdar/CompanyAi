
def dynamic_router(context):
    if context.get("volatility") == "high":
        return ["ForecastEngine", "MonteCarloRiskEngine"]
    if context.get("kpi_status") == "critical":
        return ["RiskEngine", "FinancialImpactEngine"]
    return ["StandardReasoning"]
