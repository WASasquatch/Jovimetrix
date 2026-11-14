"""Colour vision deficiency simulation: the seven simulators of DaltonLens.

Ported from DaltonLens-Python 0.1.5 (MIT, Nicolas Burrus). The Viénot and Brettel matrices
below are the ones DaltonLens derives from its LMS models, computed once and written out; the
Machado and Coblis tables are copied from it. Images go through linear RGB as DaltonLens does,
except Coblis V1, which works on the encoded values, and Coblis V2, which uses gamma 2.2.
"""

from __future__ import annotations

import math

import torch

from ..enums import EnumCBDeficiency, EnumCBSimulator

from .space import apply_matrix, linear_to_srgb, srgb_to_linear

#: Viénot 1999: one linear RGB matrix per deficiency.
VIENOT = {
    "PROTAN": ((0.1088893110, 0.8911106890, 0.0), (0.1088893110, 0.8911106890, 0.0),
               (0.0044713142, -0.0044713142, 1.0)),
    "DEUTAN": ((0.2903053213, 0.7096946787, 0.0), (0.2903053213, 0.7096946787, 0.0),
               (-0.0219735394, 0.0219735394, 1.0)),
    "TRITAN": ((1.0, 0.1523620092, -0.1523620092), (0.0, 0.8671732245, 0.1328267755),
               (0.0, 0.8671732245, 0.1328267755)),
}

#: Brettel 1997, Smith and Pokorny cones: two half-plane matrices and the plane separating them.
BRETTEL = {
    "PROTAN": (((0.1450961893, 1.2016532158, -0.3467494051), (0.1044650099, 0.8531639308, 0.0423710593),
                (0.0042896394, -0.0060295193, 1.0017398798)),
               ((0.1411517215, 1.1678219369, -0.3089736585), (0.1049470043, 0.8572979455, 0.0377550502),
                (0.0043094315, -0.0058597645, 1.0015503330)),
               (0.0004845495, 0.0041559296, -0.0046404791)),
    "DEUTAN": (((0.3619823932, 0.8675466623, -0.2295290555), (0.2609853390, 0.6451242766, 0.0938903844),
                (-0.0197542767, 0.0268609465, 0.9928933302)),
               ((0.3700900098, 0.8854017913, -0.2554918011), (0.2576688646, 0.6378205175, 0.1045106179),
                (-0.0195032490, 0.0274137763, 0.9920894726)),
               (-0.0029279800, -0.0064481911, 0.0093761711)),
    "TRITAN": (((1.0135416153, 0.1426823107, -0.1562239260), (-0.0118053648, 0.8756118317, 0.1361935331),
                (0.0770725345, 0.8120809125, 0.1108465530)),
               ((0.9333697629, 0.1999900499, -0.1333598129), (0.0580871806, 0.8256518564, 0.1162609631),
                (-0.3792281148, 1.1382497342, 0.2409783807)),
               (0.0396009507, -0.0283072037, -0.0112937470)),
}

#: Brettel 1997 with Vischeck's cones and anchors, as GIMP's Vischeck filter does it.
VISCHECK = {
    "PROTAN": (((0.2061145818, 0.9919181468, -0.1980327285), (0.1668959304, 0.7914722979, 0.0416317717),
                (0.0096738609, -0.0120869813, 1.0024131204)),
               ((0.2099271218, 1.0114039731, -0.2213310950), (0.1660944326, 0.7873758564, 0.0465297109),
                (0.0096274034, -0.0123244251, 1.0026970217)),
               (0.0012366342, 0.0063204158, -0.0075570500)),
    "DEUTAN": (((0.4354898574, 0.7226520704, -0.1581419277), (0.3352239765, 0.5708663453, 0.0939096782),
                (-0.0226893709, 0.0290455736, 0.9936437974)),
               ((0.4292196681, 0.7131600556, -0.1423797237), (0.3389474132, 0.5765030038, 0.0845495830),
                (-0.0229413888, 0.0286640608, 0.9942773280)),
               (-0.0038308759, -0.0057993035, 0.0096301793)),
    "TRITAN": (((1.0137183149, 0.0854882004, -0.0992065153), (-0.0215734913, 0.8655608239, 0.1560126674),
                (0.1215870557, 0.7576920831, 0.1207208612)),
               ((0.9489089103, 0.1343208503, -0.0832297606), (0.0803461059, 0.7887663519, 0.1308875421),
                (-0.4528264019, 1.1905016641, 0.2623247378)),
               (0.0034039007, -0.0025647743, -0.0008391265)),
}

#: Machado 2009, severity 0.0 to 1.0 in steps of 0.1.
MACHADO = {
    "PROTAN": (
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.856167, 0.182038, -0.038205), (0.029342, 0.955115, 0.015544), (-0.002880, -0.001563, 1.004443)),
        ((0.734766, 0.334872, -0.069637), (0.051840, 0.919198, 0.028963), (-0.004928, -0.004209, 1.009137)),
        ((0.630323, 0.465641, -0.095964), (0.069181, 0.890046, 0.040773), (-0.006308, -0.007724, 1.014032)),
        ((0.539009, 0.579343, -0.118352), (0.082546, 0.866121, 0.051332), (-0.007136, -0.011959, 1.019095)),
        ((0.458064, 0.679578, -0.137642), (0.092785, 0.846313, 0.060902), (-0.007494, -0.016807, 1.024301)),
        ((0.385450, 0.769005, -0.154455), (0.100526, 0.829802, 0.069673), (-0.007442, -0.022190, 1.029632)),
        ((0.319627, 0.849633, -0.169261), (0.106241, 0.815969, 0.077790), (-0.007025, -0.028051, 1.035076)),
        ((0.259411, 0.923008, -0.182420), (0.110296, 0.804340, 0.085364), (-0.006276, -0.034346, 1.040622)),
        ((0.203876, 0.990338, -0.194214), (0.112975, 0.794542, 0.092483), (-0.005222, -0.041043, 1.046265)),
        ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    ),
    "DEUTAN": (
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.866435, 0.177704, -0.044139), (0.049567, 0.939063, 0.011370), (-0.003453, 0.007233, 0.996220)),
        ((0.760729, 0.319078, -0.079807), (0.090568, 0.889315, 0.020117), (-0.006027, 0.013325, 0.992702)),
        ((0.675425, 0.433850, -0.109275), (0.125303, 0.847755, 0.026942), (-0.007950, 0.018572, 0.989378)),
        ((0.605511, 0.528560, -0.134071), (0.155318, 0.812366, 0.032316), (-0.009376, 0.023176, 0.986200)),
        ((0.547494, 0.607765, -0.155259), (0.181692, 0.781742, 0.036566), (-0.010410, 0.027275, 0.983136)),
        ((0.498864, 0.674741, -0.173604), (0.205199, 0.754872, 0.039929), (-0.011131, 0.030969, 0.980162)),
        ((0.457771, 0.731899, -0.189670), (0.226409, 0.731012, 0.042579), (-0.011595, 0.034333, 0.977261)),
        ((0.422823, 0.781057, -0.203881), (0.245752, 0.709602, 0.044646), (-0.011843, 0.037423, 0.974421)),
        ((0.392952, 0.823610, -0.216562), (0.263559, 0.690210, 0.046232), (-0.011910, 0.040281, 0.971630)),
        ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    ),
    "TRITAN": (
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.926670, 0.092514, -0.019184), (0.021191, 0.964503, 0.014306), (0.008437, 0.054813, 0.936750)),
        ((0.895720, 0.133330, -0.029050), (0.029997, 0.945400, 0.024603), (0.013027, 0.104707, 0.882266)),
        ((0.905871, 0.127791, -0.033662), (0.026856, 0.941251, 0.031893), (0.013410, 0.148296, 0.838294)),
        ((0.948035, 0.089490, -0.037526), (0.014364, 0.946792, 0.038844), (0.010853, 0.193991, 0.795156)),
        ((1.017277, 0.027029, -0.044306), (-0.006113, 0.958479, 0.047634), (0.006379, 0.248708, 0.744913)),
        ((1.104996, -0.046633, -0.058363), (-0.032137, 0.971635, 0.060503), (0.001336, 0.317922, 0.680742)),
        ((1.193214, -0.109812, -0.083402), (-0.058496, 0.979410, 0.079086), (-0.002346, 0.403492, 0.598854)),
        ((1.257728, -0.139648, -0.118081), (-0.078003, 0.975409, 0.102594), (-0.003316, 0.501214, 0.502102)),
        ((1.278864, -0.125333, -0.153531), (-0.084748, 0.957674, 0.127074), (-0.000989, 0.601151, 0.399838)),
        ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
    ),
}

#: Coblis V1, applied to the encoded values.
COBLIS_V1 = {
    "PROTAN": ((0.567, 0.433, 0.0), (0.558, 0.442, 0.0), (0.0, 0.242, 0.758)),
    "DEUTAN": ((0.625, 0.375, 0.0), (0.700, 0.300, 0.0), (0.0, 0.300, 0.700)),
    "TRITAN": ((0.950, 0.050, 0.0), (0.0, 0.433, 0.567), (0.0, 0.475, 0.525)),
}

#: Coblis V2 confusion point and axis constants.
COBLIS_V2 = {
    "PROTAN": (0.735, 0.265, 1.273463, -0.073894),
    "DEUTAN": (1.140, -0.140, 0.968437, 0.003331),
    "TRITAN": (0.171, -0.003, 0.062921, 0.292119),
}

_COBLIS_RGB2XYZ = ((0.430574, 0.341550, 0.178325), (0.222015, 0.706655, 0.071330),
                   (0.020183, 0.129553, 0.939180))
_COBLIS_XYZ2RGB = ((3.063218, -1.393325, -0.475802), (-0.969243, 1.875966, 0.041555),
                   (0.067871, -0.228834, 1.069251))

# ==============================================================================
# === SIMULATORS ===
# ==============================================================================

def _brettel(lin: torch.Tensor, table: dict, name: str) -> torch.Tensor:
    m1, m2, n = table[name]
    side = (lin @ torch.tensor(n, dtype=lin.dtype, device=lin.device)) < 0
    return torch.where(side.unsqueeze(-1), apply_matrix(lin, m2), apply_matrix(lin, m1))


def _machado(lin: torch.Tensor, name: str, severity: float) -> torch.Tensor:
    lower = int(math.floor(severity * 10.0))
    upper = min(lower + 1, 10)
    m1 = torch.tensor(MACHADO[name][lower], dtype=torch.float64)
    m2 = torch.tensor(MACHADO[name][upper], dtype=torch.float64)
    t = severity - lower / 10.0
    return apply_matrix(lin, (t * m2 + (1.0 - t) * m1).tolist())


def _coblis_v2(lin: torch.Tensor, name: str) -> torch.Tensor:
    cpu, cpv, am, ayi = COBLIS_V2[name]
    wx, wy, wz = 0.312713, 0.329016, 0.358271
    xyz = apply_matrix(lin, _COBLIS_RGB2XYZ)
    cx, cy = xyz[..., 0], xyz[..., 1]
    total = xyz.sum(-1)
    ok = total != 0
    safe = torch.where(ok, total, torch.ones_like(total))
    cu = torch.where(ok, cx / safe, torch.zeros_like(cx))
    cv = torch.where(ok, cy / safe, torch.zeros_like(cy))
    nx = wx * cy / wy
    nz = wz * cy / wy
    clm = (cpv - cv) / (cpu - cu)
    clyi = cv - cu * clm
    du = (ayi - clyi) / (clm - am)
    dv = clm * du + clyi
    sx = du * cy / dv
    sz = (1.0 - (du + dv)) * cy / dv
    srgb = apply_matrix(torch.stack([sx, cy, sz], dim=-1), _COBLIS_XYZ2RGB)
    drgb = apply_matrix(torch.stack([nx - sx, torch.zeros_like(cy), nz - sz], dim=-1), _COBLIS_XYZ2RGB)
    target = torch.where(srgb < 0, torch.zeros_like(srgb), torch.ones_like(srgb))
    adjust = torch.nan_to_num((target - srgb) / drgb, nan=0.0, posinf=0.0, neginf=0.0)
    adjust = torch.where((adjust > 1) | (adjust < 0), torch.zeros_like(adjust), adjust)
    out = srgb + drgb * adjust.amax(-1, keepdim=True)
    return torch.nan_to_num(out, nan=0.0, posinf=1.0, neginf=0.0)


def simulate(rgb: torch.Tensor, deficiency: EnumCBDeficiency,
             simulator: EnumCBSimulator = EnumCBSimulator.AUTOSELECT,
             severity: float = 1.0) -> torch.Tensor:
    """Show how an RGB frame looks with a colour vision deficiency.

    Args:
        rgb: ``(H, W, 3)`` frame, 0 to 1.
        deficiency: Protan, deutan or tritan.
        simulator: Model; AUTOSELECT picks Brettel for tritan, Machado below full severity,
            and Viénot otherwise.
        severity: 0 leaves the frame alone; 1 is full dichromacy.

    Returns:
        The simulated frame, 0 to 1.
    """
    name = deficiency.value
    severity = float(min(1.0, max(0.0, severity)))
    if simulator == EnumCBSimulator.AUTOSELECT:
        if deficiency == EnumCBDeficiency.TRITAN:
            simulator = EnumCBSimulator.BRETTEL1997
        elif severity < 0.999:
            simulator = EnumCBSimulator.MACHADO2009
        else:
            simulator = EnumCBSimulator.VIENOT1999

    work = rgb.double()
    if simulator == EnumCBSimulator.COBLISV1:
        lin = work
    elif simulator == EnumCBSimulator.COBLISV2:
        lin = work.clamp(min=0) ** 2.2
    else:
        lin = srgb_to_linear(work)

    if simulator == EnumCBSimulator.MACHADO2009:
        out = _machado(lin, name, severity)
    else:
        if simulator == EnumCBSimulator.VIENOT1999:
            full = apply_matrix(lin, VIENOT[name])
        elif simulator == EnumCBSimulator.BRETTEL1997:
            full = _brettel(lin, BRETTEL, name)
        elif simulator == EnumCBSimulator.VISCHECK:
            full = _brettel(lin, VISCHECK, name)
        elif simulator == EnumCBSimulator.COBLISV1:
            full = apply_matrix(lin, COBLIS_V1[name])
        else:
            full = _coblis_v2(lin, name)
        out = full if severity >= 0.99999 else full * severity + lin * (1.0 - severity)

    if simulator == EnumCBSimulator.COBLISV1:
        out = out.clamp(0, 1)
    elif simulator == EnumCBSimulator.COBLISV2:
        out = out.clamp(0, 1) ** (1 / 2.2)
    else:
        out = linear_to_srgb(out)
    return out.to(rgb.dtype)
