from __future__ import annotations

import math
from typing import Any, TypedDict


class PlacedPlayer(TypedDict, total=False):
    player_id: str
    x: float
    y: float


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _softmax(logits: list[float]) -> list[float]:
    if not logits:
        return []
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]


def _role_attack_weight(pos_group: str) -> float:
    return {"FW": 1.0, "MF": 0.82, "DF": 0.42, "GK": 0.06}.get(pos_group, 0.55)


def _role_defense_weight(pos_group: str) -> float:
    return {"DF": 1.0, "MF": 0.68, "FW": 0.22, "GK": 0.12}.get(pos_group, 0.5)


def _gk_zone_weight(x: float, *, home_side: bool) -> float:
    """Peak near own goal line; home defends x≈0, away defends x≈1."""
    gx = 0.08 if home_side else 0.92
    sigma = 0.11
    return math.exp(-((x - gx) ** 2) / (2 * sigma**2))


def _gk_misfit(x: float, *, home_side: bool) -> float:
    """1 = perfect for GK; decays when dragged forward."""
    ideal = 0.06 if home_side else 0.94
    dist = abs(x - ideal)
    return math.exp(-4.2 * dist)


def _team_strength(
    placements: list[PlacedPlayer],
    players_by_id: dict[str, dict[str, Any]],
    *,
    home_side: bool,
) -> tuple[float, list[dict[str, Any]]]:
    total = 0.0
    breakdown: list[dict[str, Any]] = []
    for p in placements:
        pid = str(p.get("player_id", "")).strip()
        x = _clamp01(float(p.get("x", 0.5)))
        y = _clamp01(float(p.get("y", 0.5)))
        row = players_by_id.get(pid)
        if row is None:
            breakdown.append({"player_id": pid, "skipped": True, "reason": "unknown_id"})
            continue

        pos_group = str(row.get("pos_group", "MF"))
        atk = float(row.get("atk_index", row.get("rating", 70)))
        defe = float(row.get("def_index", row.get("rating", 70)))
        gk = float(row.get("gk_index", 12.0))

        if home_side:
            w_att_x = 0.22 + 0.78 * x
            w_def_x = 0.22 + 0.78 * (1.0 - x)
        else:
            w_att_x = 0.22 + 0.78 * (1.0 - x)
            w_def_x = 0.22 + 0.78 * x
        w_y = 0.86 + 0.28 * (1.0 - 2.0 * abs(y - 0.5))

        if pos_group == "GK":
            zone = _gk_zone_weight(x, home_side=home_side)
            fit = _gk_misfit(x, home_side=home_side)
            misuse = fit * (0.18 + 0.82 * zone)
            contrib = gk * zone * w_y * (0.55 + 0.45 * fit) + atk * 0.04 * w_att_x * (1.0 - zone)
        else:
            att_part = atk * w_att_x * w_y * _role_attack_weight(pos_group)
            def_part = defe * w_def_x * w_y * _role_defense_weight(pos_group)
            gk_spill = gk * _gk_zone_weight(x, home_side=home_side) * 0.04 * (1.0 if pos_group == "DF" else 0.35)
            misuse_pen = 1.0
            if pos_group == "FW" and w_def_x > 0.78:
                misuse_pen *= 0.72
            if pos_group == "DF" and w_att_x > 0.78:
                misuse_pen *= 0.78
            contrib = (att_part + def_part + gk_spill) * misuse_pen

        total += contrib
        breakdown.append(
            {
                "player_id": pid,
                "name": row.get("name"),
                "pos_group": pos_group,
                "x": x,
                "y": y,
                "contribution": round(contrib, 4),
            }
        )
    return total, breakdown


def predict_lineup_match(
    home: list[PlacedPlayer],
    away: list[PlacedPlayer],
    players_by_id: dict[str, dict[str, Any]],
    *,
    referee: dict[str, Any] | None = None,
    home_logit_bias: float = 0.22,
    draw_sharpness: float = 0.032,
    draw_base: float = 0.42,
    strength_scale: float = 0.038,
) -> dict[str, Any]:
    """
    Lineup-aware heuristic: atk/def/gk indices × pitch coordinates × role weights.
    Optional referee: empirical H/D/A biases only (on-pitch position does not matter).
    """
    t_h, br_h = _team_strength(home, players_by_id, home_side=True)
    t_a, br_a = _team_strength(away, players_by_id, home_side=False)
    diff = abs(t_h - t_a)
    h_logit = strength_scale * t_h + home_logit_bias
    a_logit = strength_scale * t_a
    d_logit = draw_base - draw_sharpness * diff

    ref_note: dict[str, Any] | None = None
    if referee:
        bh = float(referee.get("bias_h", 0) or 0)
        bd = float(referee.get("bias_d", 0) or 0)
        ba = float(referee.get("bias_a", 0) or 0)
        h_logit += bh
        d_logit += bd
        a_logit += ba
        ref_note = {
            "bias_applied": {"h": bh, "d": bd, "a": ba},
        }

    probs = _softmax([h_logit, d_logit, a_logit])
    labels = ["H", "D", "A"]
    prediction = labels[int(max(range(3), key=lambda i: probs[i]))]

    meta = {
        "framework": "board_lineup_understat_indices_v1",
        "note": "Heuristic over scraped season indices; referee offsets from football-data E0 fit.",
        "referee": ref_note,
    }
    return {
        "prediction": prediction,
        "probabilities": {labels[i]: round(probs[i], 6) for i in range(3)},
        "team_strength": {"home": round(t_h, 4), "away": round(t_a, 4)},
        "breakdown": {"home": br_h, "away": br_a},
        "meta": meta,
    }
