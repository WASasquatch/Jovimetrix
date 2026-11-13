"""Every enumeration a node schema offers as a menu.

Member names are the menu entries saved in workflows. An integer value standing for an OpenCV
constant equals that constant.
"""

from __future__ import annotations

from enum import Enum

# ==============================================================================
# === VALUE TYPES ===
# ==============================================================================

class EnumConvertType(Enum):
    BOOLEAN = 0
    INT = 10
    FLOAT = 12
    VEC2 = 20
    VEC3 = 30
    VEC4 = 40
    VEC2INT = 25
    VEC3INT = 35
    VEC4INT = 45
    STRING = 50
    LIST = 60
    DICT = 65
    IMAGE = 70
    MASK = 75
    LATENT = 80
    ANY = 70

class EnumFillOperation(Enum):
    DEFAULT = 0
    FILL_ZERO = 20
    FILL_ALL = 10

class EnumImageType(Enum):
    GRAYSCALE = 0
    RGB = 10
    RGBA = 20
    BGR = 30
    BGRA = 40

# ==============================================================================
# === ADJUST ===
# ==============================================================================

class EnumAdjustBlur(Enum):
    BLUR = 10
    STACK_BLUR = 20
    GAUSSIAN_BLUR = 30
    MEDIAN_BLUR = 40

class EnumAdjustColor(Enum):
    RGB = 10
    HSV = 20
    YUV = 30
    LAB = 40
    LUV = 50
    XYZ = 60

class EnumAdjustEdge(Enum):
    OUTLINE = 20
    CANNY = 30
    LAPLACIAN = 40
    SOBEL = 50
    PREWITT = 60
    SCHARR = 70

class EnumAdjustMorpho(Enum):
    DILATE = 10
    ERODE = 20
    OPEN = 30
    CLOSE = 40
    TOPHAT = 50
    BLACKHAT = 60

class EnumAdjustLight(Enum):
    EXPOSURE = 10
    GAMMA = 20
    BRIGHTNESS = 30
    CONTRAST = 40
    EQUALIZE = 50

class EnumAdjustPixel(Enum):
    PIXELATE = 10
    PIXELSCALE = 20
    QUANTIZE = 30
    POSTERIZE = 40

class EnumAutoLevel(Enum):
    MANUAL = 10
    AUTO = 20
    HISTOGRAM = 30

class EnumThreshold(Enum):
    BINARY = 0
    TRUNC = 2
    TOZERO = 3

class EnumThresholdAdapt(Enum):
    ADAPT_NONE = -1
    ADAPT_MEAN = 0
    ADAPT_GAUSS = 1

# ==============================================================================
# === CHANNEL AND PIXEL ===
# ==============================================================================

class EnumPixelSwizzle(Enum):
    RED_A = 0
    GREEN_A = 10
    BLUE_A = 20
    ALPHA_A = 30
    RED_B = 1
    GREEN_B = 11
    BLUE_B = 21
    ALPHA_B = 31
    CONSTANT = 52

class EnumGrayscaleCrunch(Enum):
    LOW = 0
    HIGH = 1
    MEAN = 2

class EnumPrecision(Enum):
    FLOAT = 0
    INT = 1

# ==============================================================================
# === COLOR ===
# ==============================================================================

class EnumColorMap(Enum):
    AUTUMN = 0
    BONE = 1
    JET = 2
    WINTER = 3
    RAINBOW = 4
    OCEAN = 5
    SUMMER = 6
    SPRING = 7
    COOL = 8
    HSV = 9
    PINK = 10
    HOT = 11
    PARULA = 12
    MAGMA = 13
    INFERNO = 14
    PLASMA = 15
    VIRIDIS = 16
    CIVIDIS = 17
    TWILIGHT = 18
    TWILIGHT_SHIFTED = 19
    TURBO = 20
    DEEPGREEN = 21

class EnumColorTheory(Enum):
    COMPLIMENTARY = 0
    MONOCHROMATIC = 1
    SPLIT_COMPLIMENTARY = 2
    ANALOGOUS = 3
    TRIADIC = 4
    SQUARE = 6
    COMPOUND = 8
    CUSTOM_TETRAD = 9

class EnumCBDeficiency(Enum):
    PROTAN = "PROTAN"
    DEUTAN = "DEUTAN"
    TRITAN = "TRITAN"

class EnumCBSimulator(Enum):
    AUTOSELECT = 0
    BRETTEL1997 = 1
    COBLISV1 = 2
    COBLISV2 = 3
    MACHADO2009 = 4
    VIENOT1999 = 5
    VISCHECK = 6

class EnumColorMatchMode(Enum):
    REINHARD = 30
    LUT = 10

class EnumColorMatchMap(Enum):
    USER_MAP = 0
    PRESET_MAP = 10

# ==============================================================================
# === COMPOSE ===
# ==============================================================================

class EnumBlendType(Enum):
    """Menu names, each valued with the matching ``blendmodes`` member name."""
    NORMAL = "NORMAL"
    ADDITIVE = "ADDITIVE"
    NEGATION = "NEGATION"
    DIFFERENCE = "DIFFERENCE"
    MULTIPLY = "MULTIPLY"
    DIVIDE = "DIVIDE"
    LIGHTEN = "LIGHTEN"
    DARKEN = "DARKEN"
    SCREEN = "SCREEN"
    BURN = "COLOURBURN"
    DODGE = "COLOURDODGE"
    OVERLAY = "OVERLAY"
    HUE = "HUE"
    SATURATION = "SATURATION"
    LUMINOSITY = "LUMINOSITY"
    COLOR = "COLOUR"
    SOFT = "SOFTLIGHT"
    HARD = "HARDLIGHT"
    PIN = "PINLIGHT"
    VIVID = "VIVIDLIGHT"
    EXCLUSION = "EXCLUSION"
    REFLECT = "REFLECT"
    GLOW = "GLOW"
    XOR = "XOR"
    EXTRACT = "GRAINEXTRACT"
    MERGE = "GRAINMERGE"
    DESTIN = "DESTIN"
    DESTOUT = "DESTOUT"
    SRCATOP = "SRCATOP"
    DESTATOP = "DESTATOP"

class EnumEdge(Enum):
    CLIP = 1
    WRAP = 2
    WRAPX = 3
    WRAPY = 4

class EnumInterpolation(Enum):
    NEAREST = 0
    LINEAR = 1
    CUBIC = 2
    AREA = 3
    LANCZOS4 = 4
    LINEAR_EXACT = 5
    NEAREST_EXACT = 6

class EnumMirrorMode(Enum):
    NONE = -1
    X = 0
    FLIP_X = 10
    Y = 20
    FLIP_Y = 30
    XY = 40
    X_FLIP_Y = 50
    FLIP_XY = 60
    FLIP_X_FLIP_Y = 70

class EnumOrientation(Enum):
    HORIZONTAL = 0
    VERTICAL = 1
    GRID = 2

class EnumScaleMode(Enum):
    MATTE = 0
    CROP = 20
    FIT = 10
    ASPECT = 30
    ASPECT_SHORT = 35
    RESIZE_MATTE = 40

class EnumScaleInputMode(Enum):
    NONE = 0
    CROP = 20
    FIT = 10
    ASPECT = 30
    ASPECT_SHORT = 35
    RESIZE_MATTE = 40

class EnumImageBySize(Enum):
    LARGEST = 10
    SMALLEST = 20
    WIDTH_MIN = 30
    WIDTH_MAX = 40
    HEIGHT_MIN = 50
    HEIGHT_MAX = 60

# ==============================================================================
# === CREATE AND TRANSFORM ===
# ==============================================================================

class EnumShapes(Enum):
    CIRCLE = 0
    SQUARE = 1
    POLYGON = 4

class EnumAlignment(Enum):
    TOP = 10
    CENTER = 0
    BOTTOM = 20

class EnumJustify(Enum):
    LEFT = 10
    CENTER = 0
    RIGHT = 20

class EnumProjection(Enum):
    NORMAL = 0
    POLAR = 5
    SPHERICAL = 10
    FISHEYE = 15
    PERSPECTIVE = 20

class EnumCropMode(Enum):
    CENTER = 20
    XY = 0
    FREE = 10

# ==============================================================================
# === MATHS ===
# ==============================================================================

class EnumEase(Enum):
    NONE = 0
    LINEAR = 50

    BOUNCE_IN = 100
    BOUNCE_OUT = 101
    BOUNCE_IN_OUT = 102

    ELASTIC_IN = 80
    ELASTIC_OUT = 81
    ELASTIC_IN_OUT = 82

    BACK_IN = 90
    BACK_OUT = 91
    BACK_IN_OUT = 92

    SIN_IN = 50
    SIN_OUT = 51
    SIN_IN_OUT = 52

    CUBIC_IN = 20
    CUBIC_OUT = 21
    CUBIC_IN_OUT = 22

    QUAD_IN = 10
    QUAD_OUT = 11
    QUAD_IN_OUT = 12

    QUARTIC_IN = 30
    QUARTIC_OUT = 31
    QUARTIC_IN_OUT = 32

    QUINTIC_IN = 40
    QUINTIC_OUT = 41
    QUINTIC_IN_OUT = 42

    CIRCULAR_IN = 60
    CIRCULAR_OUT = 61
    CIRCULAR_IN_OUT = 62

    EXPONENTIAL_IN = 70
    EXPONENTIAL_OUT = 71
    EXPONENTIAL_IN_OUT = 72

class EnumNormalize(Enum):
    MINMAX1 = 0
    MINMAX2 = 1
    ZSCORE = 2
    L2 = 3

class EnumWave(Enum):
    SIN = 0
    COS = 3
    TAN = 6
    SAWTOOTH = 30
    TRIANGLE = 32
    SQUARE = 34
    PULSE = 36
    RAMP = 40
    STEP = 41
    EXPONENTIAL = 50
    LOGARITHMIC = 55
    NOISE = 60
    HAVERSINE = 70
    RECTANGULAR_PULSE = 80
    GAUSSIAN = 90
    CHIRP = 100

# ==============================================================================
# === CALC ===
# ==============================================================================

class EnumBinaryOperation(Enum):
    ADD = 0
    SUBTRACT = 1
    MULTIPLY = 2
    DIVIDE = 3
    DIVIDE_FLOOR = 4
    MODULUS = 5
    POWER = 6
    MAXIMUM = 20
    MINIMUM = 21
    DOT_PRODUCT = 30
    CROSS_PRODUCT = 31
    BIT_AND = 60
    BIT_NAND = 61
    BIT_OR = 62
    BIT_NOR = 63
    BIT_XOR = 64
    BIT_XNOR = 65
    BIT_LSHIFT = 66
    BIT_RSHIFT = 67
    UNION = 80
    INTERSECTION = 81
    DIFFERENCE = 82
    BASE = 90

class EnumComparison(Enum):
    EQUAL = 0
    NOT_EQUAL = 1
    LESS_THAN = 2
    LESS_THAN_EQUAL = 3
    GREATER_THAN = 4
    GREATER_THAN_EQUAL = 5
    AND = 20
    NAND = 21
    OR = 22
    NOR = 23
    XOR = 24
    XNOR = 25
    IS = 80
    IS_NOT = 81
    IN = 82
    NOT_IN = 83

class EnumConvertString(Enum):
    SPLIT = 10
    JOIN = 30
    FIND = 40
    REPLACE = 50
    SLICE = 70

class EnumSwizzle(Enum):
    A_X = 0
    A_Y = 10
    A_Z = 20
    A_W = 30
    B_X = 9
    B_Y = 11
    B_Z = 21
    B_W = 31
    CONSTANT = 40

class EnumUnaryOperation(Enum):
    ABS = 0
    FLOOR = 1
    CEIL = 2
    SQRT = 3
    SQUARE = 4
    LOG = 5
    LOG10 = 6
    SIN = 7
    COS = 8
    TAN = 9
    NEGATE = 10
    RECIPROCAL = 12
    FACTORIAL = 14
    EXP = 16
    MINIMUM = 20
    MAXIMUM = 21
    MEAN = 22
    MEDIAN = 24
    MODE = 26
    MAGNITUDE = 30
    NORMALIZE = 32
    NOT = 40
    BIT_NOT = 45
    COS_H = 60
    SIN_H = 62
    TAN_H = 64
    RADIANS = 70
    DEGREES = 72
    GAMMA = 80
    IS_EVEN = 90
    IS_ODD = 91

# ==============================================================================
# === BATCH ===
# ==============================================================================

class EnumBatchMode(Enum):
    MERGE = 30
    PICK = 10
    SLICE = 15
    INDEX_LIST = 20
    RANDOM = 5
