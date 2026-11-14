"""K-means clustering in torch, seeded with k-means++ and repeatable from a fixed seed."""

from __future__ import annotations

import torch

#: Points used to place the centres; larger inputs are sampled down to this many.
FIT_POINTS = 1 << 18

#: Distance entries computed at once.
CHUNK = 1 << 24


def _assign(points: torch.Tensor, centers: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    n = points.shape[0]
    labels = torch.empty(n, dtype=torch.long, device=points.device)
    dist = torch.empty(n, dtype=points.dtype, device=points.device)
    norms = (centers * centers).sum(1)
    step = max(1, CHUNK // max(1, centers.shape[0]))
    for start in range(0, n, step):
        p = points[start:start + step]
        d = (p * p).sum(1, keepdim=True) - 2.0 * (p @ centers.T) + norms
        dist[start:start + step], labels[start:start + step] = d.min(dim=1)
    return labels, dist.clamp(min=0)


def _plus_plus(points: torch.Tensor, k: int, gen: torch.Generator) -> torch.Tensor:
    n = points.shape[0]
    centers = [points[torch.randint(n, (1,), generator=gen)]]
    d2 = ((points - centers[0]) ** 2).sum(1)
    for _ in range(1, k):
        total = float(d2.sum())
        if total <= 0:
            pick = torch.randint(n, (1,), generator=gen)
        else:
            pick = torch.multinomial(d2 / total, 1, generator=gen)
        c = points[pick]
        centers.append(c)
        d2 = torch.minimum(d2, ((points - c) ** 2).sum(1))
    return torch.cat(centers, dim=0)


def kmeans(points: torch.Tensor, k: int, iterations: int = 20, epsilon: float = 0.5,
           attempts: int = 1, seed: int = 0) -> tuple[torch.Tensor, torch.Tensor]:
    """Cluster rows of ``points``.

    Args:
        points: ``(N, D)`` samples.
        k: Clusters, clamped to 1 to ``N``.
        iterations: Most refinement passes per attempt.
        epsilon: Stop once no centre moves farther than this.
        attempts: Restarts; the tightest result is kept.
        seed: Seed for the k-means++ draws.

    Returns:
        ``(centers, labels)``: ``(k, D)`` centres and one label per sample.
    """
    points = points.float()
    n = points.shape[0]
    k = int(max(1, min(k, n)))
    gen = torch.Generator(device="cpu").manual_seed(int(seed))
    fit = points
    if n > FIT_POINTS:
        fit = points[torch.randperm(n, generator=gen)[:FIT_POINTS].to(points.device)]

    best, best_score = None, None
    for _ in range(max(1, attempts)):
        centers = _plus_plus(fit, k, gen)
        for _ in range(max(1, iterations)):
            labels, _ = _assign(fit, centers)
            sums = torch.zeros_like(centers).index_add_(0, labels, fit)
            counts = torch.bincount(labels, minlength=k).unsqueeze(1).to(fit.dtype)
            moved = torch.where(counts > 0, sums / counts.clamp(min=1), centers)
            shift = float(((moved - centers) ** 2).sum(1).max())
            centers = moved
            if shift <= epsilon * epsilon:
                break
        score = float(_assign(fit, centers)[1].sum())
        if best_score is None or score < best_score:
            best, best_score = centers, score
    labels, _ = _assign(points, best)
    return best, labels
