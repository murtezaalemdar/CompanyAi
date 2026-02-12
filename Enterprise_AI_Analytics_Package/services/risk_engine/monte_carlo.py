
import numpy as np

def monte_carlo_simulation(mean, std, runs=10000):
    simulations = np.random.normal(mean, std, runs)
    probability_of_loss = np.mean(simulations < 0)
    expected_value = np.mean(simulations)
    return {
        "probability_of_loss": float(probability_of_loss),
        "expected_value": float(expected_value)
    }
