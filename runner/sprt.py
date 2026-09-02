import math

def calculate_sprt(results, elo0=0, elo1=10, alpha=0.05, beta=0.05):
    """
    Calculates the SPRT using Normalized Elo (Variance-based Normal Approximation).
    Ideal for draw-heavy games.
    """
    W, D, L = results
    N = sum(results)
    
    if N < 2: 
        return 0.0, "LIVE"

    def elo_to_expected_score(elo):
        return 1.0 / (1.0 + 10**(-elo / 400.0))

    s = (W + D / 2.0) / N

    variance = (W + D / 4.0) / N - (s ** 2)

    if variance <= 0:
        return 0.0, "LIVE"

    elo_multiplier = math.sqrt(variance / 0.25)
    
    mu0 = elo_to_expected_score(elo0 * elo_multiplier)
    mu1 = elo_to_expected_score(elo1 * elo_multiplier)
    llr = N * ((mu1 - mu0) / variance) * (s - (mu0 + mu1) / 2.0)

    A = math.log(beta / (1.0 - alpha)) 
    B = math.log((1.0 - beta) / alpha) 

    status = "LIVE"
    if llr >= B: status = "ACCEPTED (H1)"
    elif llr <= A: status = "REJECTED (H0)"

    return llr, status

# llr, status = calculate_sprt([1197, 2820, 1020])
# print(f"LLR: {llr:.4f}")
# print(f"Status: {status}")