# MCTS Formulas Reference

All formulas below are taken from Świechowski et al.'s MCTS survey. Use
these when implementing a specific enhancement — pair with
`decision-guide.md` to know *when* to reach for each one.

## 1. UCT (base tree policy)

```
a* = argmax_a [ Q(s,a) + C * sqrt( ln(N(s)) / N(s,a) ) ]
```
Section 2.2. `C ≈ sqrt(2)` as a starting point for rewards in `[0,1]`.

## 2. UCB1-Tuned

Adds the empirical variance `σ_a` of an action's score to tighten/loosen
the exploration bonus:

```
a* = argmax_a { Q(s,a) + C * sqrt( ln(N(s))/N(s,a) * min(1/4, σ_a + sqrt(2*ln(N(s))/N(s,a))) ) }
```
Section 2.2 (Gelly & Wang, 2006).

## 3. RAVE (Rapid Action Value Estimation)

Blends the normal UCT estimate with an AMAF ("all moves as first")
estimate `Q_RAVE`, which pools statistics for an action across *all*
simulations where it was played, not just ones reached via selection:

```
Z(s,a) = (1 - β(s,a)) * W(s,a)/N(s,a)  +  β(s,a) * W_RAVE(s,a)/N_RAVE(s,a)
```
where `β(s,a)` decays from 1 to 0 as `N(s,a)` grows. A common closed form:
```
weight = sqrt( k / (3*N(s) + k) )
combined = weight * Q_RAVE(s,a) + (1 - weight) * Q(s,a)
```
`k` = RAVE equivalence constant (tune empirically). Section 2.2 / 3.2.
Useful when many actions have position-independent value (classic case:
Go). Often paired with **Transposition Tables** (Section 2.3) to detect
states reachable via multiple action sequences.

## 4. Progressive Bias

Adds a heuristic term that fades out as visits accumulate:
```
P = W * H_i / (T_i * (1 - X̄_i) + 1)
```
`H_i` = heuristic value, `X̄_i` = average reward, `T_i` = visit count,
`W` = constant controlling bias strength. Section 3.1. Good for injecting
a cheap heuristic without it dominating once real statistics accumulate.

## 5. Sufficiency threshold (tactical-trap mitigation)

Replaces the constant `C` with a switch that turns exploration off once an
action looks "good enough", to avoid positive feedback loops on
optimistic-but-refutable tactical lines:
```
C_hat = C   if all Q(s,a) <= alpha
      = 0   if any Q(s,a) > alpha
```
Section 3.2. Useful for chess-like games with many tactical traps.

## 6. Early-termination evaluation blend

Replaces `Q(s,a)` in UCT with a mix of the rollout return and an implicit
minimax evaluation, to avoid needing full random playouts to a terminal
state:
```
Q_hat(s,a) = (1-alpha) * r_s,a^tau / n_s,a  +  alpha * v_s,a^tau
```
`v^tau` = minimax evaluation for player tau, maintained alongside normal
stats. Section 3.3. Useful when full playouts are too slow (real-time
games) but a cheap evaluation function or shallow minimax is available.

## 7. AlphaGo / AlphaZero-style PUCT selection

Used when a policy network `P(s,a)` provides prior probabilities over
actions:
```
a* = argmax_a [ Q(s,a) + P(s,a) * sqrt(N(s)) / (1 + N(s,a)) ]
```
Section 5.2 (Eq. 11). Leaf evaluation blends a value network with a
rollout return:
```
V(s_L) = (1-lambda) * v_theta(s_L) + lambda * z_L
```
`v_theta` = value-network estimate, `z_L` = rollout result, `lambda` =
mixing parameter. Requires trained policy/value networks — see
`decision-guide.md` → "MCTS + Neural Networks" for when this is worth it.

## 8. Knowledge-bias UCT (human-style priors without full PUCT)

A lighter-weight alternative to PUCT for injecting a trained prior `P(m_i)`
(e.g., predicting human-like moves) into UCT:
```
a* = argmax_a [ Q(s,a) + C*sqrt(ln(N(s))/N(s,a)) + C_BT * sqrt(K/(N(s)+K)) * P(m_i) ]
```
`C_BT` = bias weight, `K` = decay-rate constant. Section 4.6.

## 9. TD-UCT (temporal-difference blended value)

Replaces/augments `Q` with a temporal-difference value estimate `V`,
updated in backpropagation via TD(λ):
```
Q_TD-UCT = omega*V + (1-omega)*Q + C*sqrt(ln(N(s))/N(s,a))
V(s_t) <- V(s_t) + alpha * e(s_t) * delta_t
delta_t = R_{t+1} + gamma*V(s_{t+1}) - V(s_t)
```
Section 5.4. Useful when you want bootstrapped value estimates instead of
(or blended with) plain Monte Carlo averages — can converge faster in some
games. Three variants exist (Single Backup, Weighted Rewards, Merged
Bootstrapping) — see `mcts-survey-source.md` Section 5.4 for details if
implementing this.

## 10. RIDE (pairwise RAVE alternative)

```
D_RIDE(a,b) = E[ Q(s,a) - Q(s,b) | s in S ]
```
Section 4.4. Alternative to RAVE's independent-sampling assumption; uses
pairwise action-value differences instead.
