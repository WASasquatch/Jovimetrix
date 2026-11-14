"""Coordinate remaps: polar, spherical, fisheye and perspective projections."""

from __future__ import annotations

import math

import torch

from . import TAU, Coord2D_Float, ImageType

from .sample import perspective_matrix, polar_inverse, remap, warp_perspective

# ==============================================================================
# === SUPPORT ===
# ==============================================================================

def _three(image: ImageType) -> ImageType:
    """Grey frames are remapped as RGB, as 2.x did."""
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    return image.expand(-1, -1, 3) if image.shape[2] == 1 else image


def coord_fisheye(width: int, height: int, distortion: float) -> tuple[torch.Tensor, torch.Tensor]:
    """Source coordinates for a barrel (positive) or pincushion (negative) distortion."""
    map_y, map_x = torch.meshgrid(torch.linspace(0., 1., height, dtype=torch.float64),
                                  torch.linspace(0., 1., width, dtype=torch.float64), indexing="ij")
    xnd, ynd = 2 * map_x - 1, 2 * map_y - 1
    dist = 1 - distortion * (xnd ** 2 + ynd ** 2)
    flat = dist == 0
    safe = torch.where(flat, torch.ones_like(dist), dist)
    xdu = torch.where(flat, xnd, xnd / safe)
    ydu = torch.where(flat, ynd, ynd / safe)
    return (xdu + 1) * width / 2, (ydu + 1) * height / 2


def coord_perspective(width: int, height: int, pts: list[Coord2D_Float]) -> list[list[float]]:
    """Homography taking the frame's corners to ``pts`` (top left, top right, bottom right, bottom left)."""
    corners = [(0, 0), (width, 0), (width, height), (0, height)]
    return perspective_matrix(corners, [(float(x), float(y)) for x, y in pts])


def coord_sphere(width: int, height: int, radius: float) -> tuple[torch.Tensor, torch.Tensor]:
    """Source coordinates that wrap a frame around a sphere of ``radius``."""
    phi, theta = torch.meshgrid(torch.linspace(0, math.pi, height, dtype=torch.float64),
                                torch.linspace(0, TAU, width, dtype=torch.float64), indexing="ij")
    x = radius * torch.sin(phi) * torch.cos(theta)
    y = radius * torch.sin(phi) * torch.sin(theta)
    return (x + 1) * (width - 1) / 2, (y + 1) * (height - 1) / 2


def remap_fisheye(image: ImageType, distort: float) -> ImageType:
    """Fisheye distortion, black outside."""
    image = _three(image)
    height, width = image.shape[:2]
    return remap(image, *coord_fisheye(width, height, distort))


def remap_perspective(image: ImageType, pts: list) -> ImageType:
    """Move the frame's corners to ``pts``, black outside."""
    image = _three(image)
    height, width = image.shape[:2]
    return warp_perspective(image, coord_perspective(width, height, pts), width, height)


def remap_polar(image: ImageType) -> ImageType:
    """Wrap the frame into a disc: columns become radius, rows become angle."""
    h, w = image.shape[:2]
    return polar_inverse(image if image.ndim == 3 else image.unsqueeze(-1), (w // 2, h // 2), max(w, h) // 2)


def remap_sphere(image: ImageType, radius: float) -> ImageType:
    """Wrap the frame around a sphere, black outside."""
    if image.ndim == 2:
        image = image.unsqueeze(-1)
    height, width = image.shape[:2]
    return remap(image, *coord_sphere(width, height, radius))
