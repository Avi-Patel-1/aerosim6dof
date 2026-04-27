"""Linear control utilities built on NumPy."""

from __future__ import annotations

from typing import Any

import numpy as np


def controllability_matrix(a_mat: np.ndarray, b_mat: np.ndarray) -> np.ndarray:
    """Return the continuous-time controllability matrix [B AB A^2B ...]."""

    n = a_mat.shape[0]
    blocks = [b_mat]
    power = np.eye(n)
    for _ in range(1, n):
        power = power @ a_mat
        blocks.append(power @ b_mat)
    return np.concatenate(blocks, axis=1)


def controllability_rank(a_mat: np.ndarray, b_mat: np.ndarray, tol: float = 1e-9) -> int:
    return int(np.linalg.matrix_rank(controllability_matrix(a_mat, b_mat), tol=tol))


def discrete_lqr(
    a_mat: np.ndarray,
    b_mat: np.ndarray,
    q_mat: np.ndarray,
    r_mat: np.ndarray,
    iterations: int = 200,
    tolerance: float = 1e-10,
) -> dict[str, Any]:
    """Solve a discrete LQR problem with Riccati iteration."""

    p_mat = q_mat.copy()
    gain = np.zeros((b_mat.shape[1], a_mat.shape[0]))
    for _ in range(iterations):
        bt_p = b_mat.T @ p_mat
        gain_next = np.linalg.solve(r_mat + bt_p @ b_mat, bt_p @ a_mat)
        p_next = q_mat + a_mat.T @ p_mat @ a_mat - a_mat.T @ p_mat @ b_mat @ gain_next
        if float(np.linalg.norm(p_next - p_mat)) < tolerance:
            gain = gain_next
            p_mat = p_next
            break
        gain = gain_next
        p_mat = p_next
    eigs = np.linalg.eigvals(a_mat - b_mat @ gain)
    return {"K": gain, "P": p_mat, "closed_loop_eigenvalues": eigs}


def lqr_summary(a_mat: np.ndarray, b_mat: np.ndarray) -> dict[str, Any]:
    n = a_mat.shape[0]
    m = b_mat.shape[1]
    q_mat = np.eye(n)
    r_mat = np.eye(m)
    solution = discrete_lqr(a_mat, b_mat, q_mat, r_mat)
    return {
        "states": n,
        "controls": m,
        "controllability_rank": controllability_rank(a_mat, b_mat),
        "gain_shape": list(solution["K"].shape),
        "closed_loop_eigenvalues_real": [float(x.real) for x in solution["closed_loop_eigenvalues"]],
        "closed_loop_eigenvalues_imag": [float(x.imag) for x in solution["closed_loop_eigenvalues"]],
    }

