from src.skills.monte_carlo import MonteCarloOptionEvaluatorSkill
import json
skill = MonteCarloOptionEvaluatorSkill()
# S=150, K=155, 35 DTE, Call, .00 premium
res = skill.execute('AAPL', 150.0, 155.0, 35, 'C', 3.00)
print(json.dumps(res, indent=2))
