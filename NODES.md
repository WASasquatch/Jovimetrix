# Jovimetrix node reference

53 nodes, by menu category. Each entry lists the node's id as saved in workflows, its inputs and its outputs.

- [ADJUST](#adjust) (9)
- [ANIMATION](#animation) (2)
- [CALC](#calc) (7)
- [COLOR](#color) (5)
- [COMPOSE](#compose) (7)
- [CREATE](#create) (3)
- [TRANSFORM](#transform) (5)
- [UTILITY/BATCH](#utilitybatch) (4)
- [UTILITY/INFO](#utilityinfo) (3)
- [UTILITY/IO](#utilityio) (4)
- [VARIABLE](#variable) (4)

## ADJUST

<details>
<summary><b>ADJUST: BLUR</b> &nbsp; <code>ADJUST: BLUR (JOV)</code></summary>

Soften a picture with a box, stack, Gaussian or median blur. Median blur removes speckle noise while keeping edges.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `func` | COMBO | BLUR | menu: `BLUR`, `STACK_BLUR`, `GAUSSIAN_BLUR`, `MEDIAN_BLUR` | BLUR = box average; STACK_BLUR = fast near-Gaussian; GAUSSIAN_BLUR = smooth falloff; MEDIAN_BLUR = removes speckles and keeps edges. |
| `radius` | INT | 3 | 3 to 1023 | Size of the blur in pixels. Even values are raised to the next odd number. 3 = slight; 31 = heavy. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>ADJUST: COLOR</b> &nbsp; <code>ADJUST: COLOR (JOV)</code></summary>

Shift a picture's three colour channels in RGB, HSV, YUV, LAB, LUV or XYZ space. Useful for hue rotation, saturation pushes and tints.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `func` | COMBO | RGB | menu: `RGB`, `HSV`, `YUV`, `LAB`, `LUV`, `XYZ` | Colour space the three shifts apply in. HSV: hue, saturation, value; LAB: lightness and two colour axes; RGB: red, green, blue. |
| `vector` | VEC3 | (0, 0, 0) | -1 to 1 | Shift for each channel of the chosen space, -1 to 1. 0 = unchanged; in HSV, x = 0.5 turns the hue half way round. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>ADJUST: EDGE</b> &nbsp; <code>ADJUST: EDGE (JOV)</code></summary>

Find the edges in a picture with Canny, Sobel, Laplacian, Prewitt, Scharr or a morphological outline. Good for line art and edge masks.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `func` | COMBO | CANNY | menu: `OUTLINE`, `CANNY`, `LAPLACIAN`, `SOBEL`, `PREWITT`, `SCHARR` | CANNY = thin clean lines; SOBEL, SCHARR, PREWITT = gradient strength; LAPLACIAN = fine detail; OUTLINE = thick shape border. |
| `radius` | INT | 1 | 1 to 1023 | Kernel size in pixels, raised to the next odd number. Larger values pick out broader edges. Sobel and Laplacian stop at 31. |
| `iter` | INT | 1 | 1 to 1000 | How many times OUTLINE grows the border. The other methods ignore it. |
| `lo-hi` | VEC2 | (0, 1) | 0 to 1 | CANNY's two thresholds, 0 to 1. Edges stronger than hi are kept; those between lo and hi are kept only when joined to a strong edge. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>ADJUST: EMBOSS</b> &nbsp; <code>ADJUST: EMBOSS (JOV)</code></summary>

Turn a picture into a raised relief lit from one direction. Useful for stamped, carved or height-map looks.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `heading` | FLOAT | -45 |  | Direction the light comes from, in degrees. 0 = right; 90 = below; 180 = left; -90 = above. |
| `elevation` | FLOAT | 45 |  | Height of the light, in degrees. 0 = grazing, deep shadows; 90 = straight down, flat. |
| `depth` | FLOAT | 10 | 0 to | How deep the relief looks. 0 = flat grey; 10 = moderate; 50 = sharp. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>ADJUST: LEVELS</b> &nbsp; <code>ADJUST: LEVELS (JOV)</code></summary>

Set a picture's black point, midtone and white point by hand, or stretch each channel so its darkest pixel becomes black and its brightest white.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `lmh` | VEC3 | (0, 0.5, 1) | 0 to 1 | MANUAL input points, 0 to 1: LOW becomes black, HIGH becomes white, MID sets the midtone. 0.5 = no midtone change; lower brightens. |
| `range` | VEC2 | (0, 1) | 0 to 1 | MANUAL output range, 0 to 1: the darkest and brightest values the result may take. (0, 1) = full range. |
| `mode` | COMBO | MANUAL | menu: `MANUAL`, `AUTO`, `HISTOGRAM` | MANUAL = use lmh and range; AUTO = stretch each channel ignoring the outer 1 percent; HISTOGRAM = stretch ignoring the share set by clip. |
| `clip` | FLOAT | 0.5 | 0 to 1.0 | HISTOGRAM only: percent of pixels ignored at each end before stretching. 0 = none; 0.5 = half a percent; 1 = one percent. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>ADJUST: LIGHT</b> &nbsp; <code>ADJUST: LIGHT (JOV)</code></summary>

Tonal adjustments applied in order: brightness, contrast, histogram equalisation, exposure and gamma. Leave a control at its default to skip it.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `brightness` | FLOAT | 0.5 | 0 to 1 | 0.5 = unchanged; 0 = black; 1 = white. |
| `contrast` | FLOAT | 0 | -1 to 1 | 0 = unchanged; -1 = flat grey; 1 = maximum contrast. |
| `equalize` | BOOLEAN | False |  | Spread the brightness histogram evenly, which lifts detail in flat or murky pictures. |
| `exposure` | FLOAT | 1 | -8 to 8 | Light is multiplied by 2 to this power, in linear light. 1 and 0 both leave the picture unchanged; 2 = four times brighter; -1 = half. |
| `gamma` | FLOAT | 1 | 0 to 8 | 1 = unchanged; above 1 brightens the midtones; below 1 darkens them; 0 = black. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>ADJUST: MORPHOLOGY</b> &nbsp; <code>ADJUST: MORPHOLOGY (JOV)</code></summary>

Grow, shrink, open or close the shapes in a picture or mask. Use it to thicken a mask, remove small specks, or fill small holes.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `func` | COMBO | DILATE | menu: `DILATE`, `ERODE`, `OPEN`, `CLOSE`, `TOPHAT`, `BLACKHAT` | DILATE = grow bright areas; ERODE = shrink them; OPEN = remove specks; CLOSE = fill holes; TOPHAT and BLACKHAT = keep only small bright or dark details. |
| `radius` | INT | 1 | 1 to 1023 | Size of the square kernel in pixels, raised to the next odd number. |
| `iter` | INT | 1 | 1 to 1000 | How many times the operation repeats. Each pass grows or shrinks by the radius again. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>ADJUST: PIXEL</b> &nbsp; <code>ADJUST: PIXEL (JOV)</code></summary>

Pixel-level effects: pixelate into blocks, rescale for a retro look, reduce to fewer colours, or posterise into bands.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `func` | COMBO | PIXELATE | menu: `PIXELATE`, `PIXELSCALE`, `QUANTIZE`, `POSTERIZE` | PIXELATE = average into blocks; PIXELSCALE = shrink then enlarge with hard edges; QUANTIZE = fewer colours by clustering; POSTERIZE = fewer brightness levels. |
| `value` | FLOAT | 0 | 0 to 1 | Strength, 0 to 1. 0 = unchanged; higher values give bigger blocks or fewer colours. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>ADJUST: SHARPEN</b> &nbsp; <code>ADJUST: SHARPEN (JOV)</code></summary>

Sharpen a picture with an unsharp mask. The threshold leaves flat, low-contrast areas such as skin and sky untouched.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to adjust: RGBA, RGB or a mask. A batch is adjusted frame by frame. With nothing connected a small black square is used. |
| `amount` | FLOAT | 0 | 0 to 1 | 0 = unchanged; 0.05 = crisp; 1 = extreme. |
| `threshold` | FLOAT | 0 | 0 to 1 | 0 = sharpen everywhere; higher values skip areas whose local contrast is below it, keeping noise in flat areas down. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

## ANIMATION

<details>
<summary><b>TICK ⏱</b> &nbsp; <code>TICK (JOV) ⏱</code></summary>

Generate a list of frame values from a start and a step, with optional looping and ping-pong, plus normalised and eased copies. Drive any number input across a batch or an animation.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `start` | FLOAT | 0 |  | First value of the series. |
| `step` | FLOAT | 0 |  | Amount added for each frame. 0 = 1; negative values count down. |
| `count` | INT | 1 | 1 to 1500 | How many values to generate. |
| `loop` | INT | 0 | 0 to | After this many values the series starts over. 0 = no loop. |
| `pingpong` | BOOLEAN | False |  | At the loop point, run back down instead of jumping to the start. |
| `ease` | COMBO | LINEAR | menu of 31 | Easing curve for the EASED outputs. LINEAR = even spacing; _IN = slow start; _OUT = slow finish; _IN_OUT = both. |
| `norm` | COMBO | MINMAX2 | menu: `MINMAX1`, `MINMAX2`, `ZSCORE`, `L2` | Normalising for the LINEAR outputs. MINMAX1 = 0 to 1; MINMAX2 = -1 to 1; ZSCORE = standard score; L2 = unit length. |
| `scalar` | FLOAT | 1 | 0 to | Multiplier for the SCALAR outputs. 1 = same as LINEAR and EASED. |

| Output | Type | Description |
|---|---|---|
| `VALUE` | FLOAT list | The raw series, start plus step per frame. |
| `LINEAR` | FLOAT list | The series normalised as set by norm. |
| `EASED` | FLOAT list | The normalised series resampled along the easing curve. |
| `SCALAR_LIN` | FLOAT list | LINEAR multiplied by scalar. |
| `SCALAR_EASE` | FLOAT list | EASED multiplied by scalar. |

</details>

<details>
<summary><b>WAVE GEN 🌊</b> &nbsp; <code>WAVE GEN (JOV) 🌊</code></summary>

Sample a sine, square, sawtooth, noise or other waveform at a point in time, as a float and an integer. Feed time from TICK to animate a value.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `wave` | COMBO | SIN | menu: `SIN`, `COS`, `TAN`, `SAWTOOTH`, `TRIANGLE`, `SQUARE`, `PULSE`, `RAMP`, `STEP`, `EXPONENTIAL`, `LOGARITHMIC`, `NOISE`, `HAVERSINE`, `RECTANGULAR_PULSE`, `GAUSSIAN`, `CHIRP` | Shape of the wave. SIN, COS, TRIANGLE and SAWTOOTH repeat smoothly; SQUARE and PULSE switch; NOISE is random; GAUSSIAN is one bump centred at freq. |
| `freq` | FLOAT | 1 | 0 to | Cycles per unit of time. 1 = one cycle as time runs 0 to 1. For GAUSSIAN, the time of the peak. |
| `amp` | FLOAT | 1 | 0 to | Height of the wave above and below its offset. |
| `phase` | FLOAT | 0 | 0 to 1 | Shift along the wave, 0 to 1. 0.5 = half a cycle later. |
| `offset` | FLOAT | 0 | 0 to 1 | Value added to every sample, which moves the whole wave up. |
| `time` | FLOAT | 0 | 0 to | The moment to sample. Wire a list of times in to get a list of samples. |
| `invert` | BOOLEAN | False |  | Flip the wave upside down around its offset. |
| `absolute` | BOOLEAN | False |  | Make every sample positive, which folds the lower half of the wave up. |

| Output | Type | Description |
|---|---|---|
| `FLOAT` | FLOAT list | The sample as a float, one per time given. |
| `INT` | INT list | The sample rounded toward zero. |

</details>

## CALC

<details>
<summary><b>BIT SPLIT ⭄</b> &nbsp; <code>BIT SPLIT (JOV) ⭄</code></summary>

Split a number or text into its separate bits, least significant first, as 0 and 1 and as booleans. Drive switches from one packed value.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `value` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Value to split. Integers use their binary form, floats their 64-bit pattern, text 8 bits per character. |
| `bits` | INT | 8 | 0 to 64 | How many bits to return, padded with 0. 0 = every bit the value has. |

| Output | Type | Description |
|---|---|---|
| `BIT` | * list | Each bit as 0 or 1. |
| `BOOL` | BOOLEAN list | Each bit as True or False. |

</details>

<details>
<summary><b>COMPARISON 🕵🏽</b> &nbsp; <code>COMPARISON (JOV) 🕵🏽</code></summary>

Compare A with B, component by component, and pass on 'success' when every component passes or 'fail' otherwise. A switch driven by a test.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `a` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | First value. Vectors compare component by component. |
| `b` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Second value. |
| `success` | * |  |  | Sent to OUT when the comparison passes. Anything can be connected; 0 when empty. |
| `fail` | * |  |  | Sent to OUT when the comparison fails. 0 when empty. |
| `func` | COMBO | EQUAL | menu: `EQUAL`, `NOT_EQUAL`, `LESS_THAN`, `LESS_THAN_EQUAL`, `GREATER_THAN`, `GREATER_THAN_EQUAL`, `AND`, `NAND`, `OR`, `NOR`, `XOR`, `XNOR`, `IS`, `IS_NOT`, `IN`, `NOT_IN` | The test. EQUAL, LESS_THAN and the like compare values; AND, OR, XOR treat them as true or false; IN asks whether each part of A is in B. |
| `swap` | BOOLEAN | False |  | Exchange A and B before comparing. |
| `invert` | BOOLEAN | False |  | Flip the result, so success and fail trade places. |

| Output | Type | Description |
|---|---|---|
| `OUT` | * list | 'success' or 'fail', depending on the result. |
| `VAL` | * list | The result of each component's test. |

</details>

<details>
<summary><b>LERP 🔰</b> &nbsp; <code>LERP (JOV) 🔰</code></summary>

Blend between two numbers or vectors by a factor, per component. 0 gives A, 1 gives B. Pair with TICK to animate between two settings.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `a` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Start value. When empty, aa is used. |
| `b` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | End value. When empty, bb is used. |
| `alpha` | VEC4 | (0.5, 0.5, 0.5, 0.5) | 0 to 1 | Blend factor for each component, 0 to 1. 0 = A; 0.5 = halfway; 1 = B. |
| `type` | COMBO | FLOAT | menu: `BOOLEAN`, `INT`, `FLOAT`, `VEC2`, `VEC3`, `VEC4` | Type of the result. FLOAT and INT use the first component; VEC2 to VEC4 use that many. |
| `aa` | VEC4 | (0, 0, 0, 0) |  | Start value used when A is not connected. |
| `bb` | VEC4 | (1, 1, 1, 1) |  | End value used when B is not connected. |

| Output | Type | Description |
|---|---|---|
| `❔` | * list | The blended value, of the type chosen in 'type'. |

</details>

<details>
<summary><b>OP BINARY 🌟</b> &nbsp; <code>OP BINARY (JOV) 🌟</code></summary>

Combine two numbers, vectors or pictures with arithmetic, minimum and maximum, dot and cross products, bitwise logic or set operations. A picture is reduced to its mean first.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `a` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4, IMAGE, MASK |  |  | First value. When empty, aa is used. |
| `b` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4, IMAGE, MASK |  |  | Second value. When empty, bb is used. |
| `func` | COMBO | ADD | menu: `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, `DIVIDE_FLOOR`, `MODULUS`, `POWER`, `MAXIMUM`, `MINIMUM`, `DOT_PRODUCT`, `CROSS_PRODUCT`, `BIT_AND`, `BIT_NAND`, `BIT_OR`, `BIT_NOR`, `BIT_XOR`, `BIT_XNOR`, `BIT_LSHIFT`, `BIT_RSHIFT`, `UNION`, `INTERSECTION`, `DIFFERENCE`, `BASE` | The operation, applied component by component. DOT_PRODUCT gives one value; CROSS_PRODUCT needs three components; UNION, INTERSECTION and DIFFERENCE treat the vectors as sets. |
| `type` | COMBO | FLOAT | menu: `BOOLEAN`, `INT`, `FLOAT`, `VEC2`, `VEC3`, `VEC4` | Type of the result. |
| `swap` | BOOLEAN | False |  | Exchange A and B first, which matters for SUBTRACT, DIVIDE, POWER and the shifts. |
| `aa` | VEC4 | (0, 0, 0, 0) |  | Value used when A is not connected. |
| `bb` | VEC4 | (0, 0, 0, 0) |  | Value used when B is not connected. |

| Output | Type | Description |
|---|---|---|
| `❔` | * list | The result, of the type chosen in 'type'. |

</details>

<details>
<summary><b>OP UNARY 🎲</b> &nbsp; <code>OP UNARY (JOV) 🎲</code></summary>

Apply a one-input function to a number, vector or picture: absolute value, rounding, roots, trigonometry, logic, or a summary such as mean, median or length. A picture is reduced to its mean first.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `a` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4, IMAGE, MASK |  |  | The value. When empty, aa is used. |
| `func` | COMBO | ABS | menu of 31 | The function, applied to each component. MEAN, MEDIAN, MODE, MAXIMUM, MINIMUM and MAGNITUDE reduce the vector to one value. |
| `type` | COMBO | FLOAT | menu: `BOOLEAN`, `INT`, `FLOAT`, `VEC2`, `VEC3`, `VEC4` | Type of the result. |
| `aa` | VEC4 | (0, 0, 0, 0) |  | Value used when A is not connected. |

| Output | Type | Description |
|---|---|---|
| `❔` | * list | The result, of the type chosen in 'type'. |

</details>

<details>
<summary><b>STRINGER 🪀</b> &nbsp; <code>STRINGER (JOV) 🪀</code></summary>

Split, join, filter, replace or slice the text wired into its growing string inputs. Each connection adds another input.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `func` | COMBO | SPLIT | menu: `SPLIT`, `JOIN`, `FIND`, `REPLACE`, `SLICE` | SPLIT = break at key; JOIN = glue with key between; FIND = keep entries holding key; REPLACE = swap key for replace; SLICE = cut each entry by range. |
| `key` | STRING |  |  | Separator for SPLIT and JOIN, or the text to look for in FIND and REPLACE. Example: ',' splits 'a,b,c' into three. |
| `replace` | STRING |  |  | Text that REPLACE puts where key was found. |
| `range` | VEC3 | (0, -1, 1) |  | SLICE start, end and step in characters. -1 as end = to the end; step -1 reverses. |

| Output | Type | Description |
|---|---|---|
| `STRING` | STRING list | The resulting text entries. |
| `COUNT` | INT | How many entries STRING holds. |

</details>

<details>
<summary><b>SWIZZLE 😵</b> &nbsp; <code>SWIZZLE (JOV) 😵</code></summary>

Build a new vector whose X, Y, Z and W each come from any component of vector A, vector B or a constant. Reorder, duplicate or mix components.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `a` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Vector A. |
| `b` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Vector B. |
| `type` | COMBO | VEC2 | menu: `VEC2`, `VEC3`, `VEC4` | Size of the result: VEC2, VEC3 or VEC4. |
| `swap x` | COMBO | A_X | menu: `A_X`, `A_Y`, `A_Z`, `A_W`, `B_X`, `B_Y`, `B_Z`, `B_W`, `CONSTANT` | Source of X: A_ or B_ and a component, or CONSTANT from 'default'. |
| `swap y` | COMBO | A_Y | menu: `A_X`, `A_Y`, `A_Z`, `A_W`, `B_X`, `B_Y`, `B_Z`, `B_W`, `CONSTANT` | Source of Y. |
| `swap z` | COMBO | A_Z | menu: `A_X`, `A_Y`, `A_Z`, `A_W`, `B_X`, `B_Y`, `B_Z`, `B_W`, `CONSTANT` | Source of Z. |
| `swap w` | COMBO | A_W | menu: `A_X`, `A_Y`, `A_Z`, `A_W`, `B_X`, `B_Y`, `B_Z`, `B_W`, `CONSTANT` | Source of W. |
| `default` | VEC4 | (0, 0, 0, 0) |  | Constants for CONSTANT sources, and for components A or B lacks. |

| Output | Type | Description |
|---|---|---|
| `❔` | * list | The new vector. |

</details>

## COLOR

<details>
<summary><b>COLOR BLIND 👁‍🗨</b> &nbsp; <code>COLOR BLIND (JOV) 👁‍🗨</code></summary>

Show how a picture looks to someone with red, green or blue colour blindness. Check that a design still reads for everyone.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to check: RGBA, RGB or a mask. |
| `mode` | COMBO | PROTAN | menu: `PROTAN`, `DEUTAN`, `TRITAN` | PROTAN = red-blind; DEUTAN = green-blind, the most common; TRITAN = blue-blind. |
| `solver` | COMBO | AUTOSELECT | menu: `AUTOSELECT`, `BRETTEL1997`, `COBLISV1`, `COBLISV2`, `MACHADO2009`, `VIENOT1999`, `VISCHECK` | Simulation model. AUTOSELECT picks the best one for the deficiency; MACHADO2009 handles partial severity well. |
| `value` | FLOAT | 1.0 | 0 to 1 | Severity. 0 = normal vision; 1 = full deficiency. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>COLOR MATCH 💞</b> &nbsp; <code>COLOR MATCH (JOV) 💞</code></summary>

Recolour a picture to match a target picture's palette, or map its tones through a built-in colour map. Keeps a sequence or a set of renders in one grade.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `source` | IMAGE, MASK |  |  | The picture to recolour. |
| `target` | IMAGE, MASK |  |  | The picture whose colours are copied. |
| `mode` | COMBO | REINHARD | menu: `REINHARD`, `LUT` | REINHARD = match the target's colour statistics, natural results; LUT = map the source's brightness through a colour table. |
| `map` | COMBO | USER_MAP | menu: `USER_MAP`, `PRESET_MAP` | LUT mode only. USER_MAP = build the table from the target's dominant colours; PRESET_MAP = use the colormap below. |
| `colormap` | COMBO | HSV | menu: `AUTUMN`, `BONE`, `JET`, `WINTER`, `RAINBOW`, `OCEAN`, `SUMMER`, `SPRING`, `COOL`, `HSV`, `PINK`, `HOT`, `PARULA`, `MAGMA`, `INFERNO`, `PLASMA`, `VIRIDIS`, `CIVIDIS`, `TWILIGHT`, `TWILIGHT_SHIFTED`, `TURBO`, `DEEPGREEN` | Built-in colour table for PRESET_MAP, such as VIRIDIS, JET or HOT. |
| `value` | INT | 255 | 0 to 255 | USER_MAP only: how many colours the table keeps. Fewer colours give a flatter, posterised look. |
| `swap` | BOOLEAN | False |  | Exchange source and target. |
| `invert` | BOOLEAN | False |  | Invert the colours of the result. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>COLOR MEANS 〰️</b> &nbsp; <code>COLOR MEANS (JOV) 〰️</code></summary>

Find a picture's most used colours and hand them on as swatches, a tonal palette, a gradient and a 3D LUT. Use them to keep other pictures in the same colour range.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to read colours from. |
| `value` | INT | 12 | 1 to 255 | How many dominant colours to find. |
| `size` | INT | 32 | 1 to 256 | Height of each row of the PALETTE output, in pixels. |
| `count` | INT | 33 | 1 to 255 | Nodes per axis of the LUT. 17 = coarse; 33 = standard; 65 = fine. |
| `wh` | VEC2 | (256, 256) | 32 to | Width and height of the IMAGE swatches and the GRADIENT; the height also sizes the RGB preview. |

| Output | Type | Description |
|---|---|---|
| `IMAGE` | IMAGE | One solid swatch per colour, most used first, as a batch. |
| `PALETTE` | IMAGE list | One row per colour, fading to black; as wide as the input. Inputs of different widths give one batch per width. |
| `GRADIENT` | IMAGE | The colours blended into one left-to-right gradient. |
| `LUT` | JLUT | A 3D LUT mapping every colour to its nearest dominant colour. |
| `RGB` | IMAGE | A picture of the LUT, one tile per blue level. |

</details>

<details>
<summary><b>COLOR THEORY 🛞</b> &nbsp; <code>COLOR THEORY (JOV) 🛞</code></summary>

Build a colour harmony, such as complementary, triadic or analogous, from a picture's average colour. Each colour comes out as a solid picture.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture whose average colour starts the harmony. |
| `scheme` | COMBO | COMPLIMENTARY | menu: `COMPLIMENTARY`, `MONOCHROMATIC`, `SPLIT_COMPLIMENTARY`, `ANALOGOUS`, `TRIADIC`, `SQUARE`, `COMPOUND`, `CUSTOM_TETRAD` | COMPLIMENTARY = opposite hue; TRIADIC = three evenly spaced; ANALOGOUS = neighbours; MONOCHROMATIC = one hue, varied shades; CUSTOM_TETRAD uses value as the spacing. |
| `value` | INT | 45 | -90 to 90 | CUSTOM_TETRAD only: separation of the colours, in degrees. |
| `invert` | BOOLEAN | False |  | Invert every colour of the harmony. |

| Output | Type | Description |
|---|---|---|
| `C1` | IMAGE list | The picture's average colour. |
| `C2` | IMAGE list | First harmony colour. |
| `C3` | IMAGE list | Second harmony colour, black when the scheme has one colour. |
| `C4` | IMAGE list | Third harmony colour, black when the scheme has fewer. |
| `C5` | IMAGE list | Fourth harmony colour, black when the scheme has fewer. |

</details>

<details>
<summary><b>GRADIENT MAP 🇲🇺</b> &nbsp; <code>GRADIENT MAP (JOV) 🇲🇺</code></summary>

Recolour a picture by its brightness: dark tones take the gradient's left colour and bright tones its right. Good for duotones, heat maps and stylised grades.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to recolour. |
| `gradient` | IMAGE, MASK |  |  | The gradient, read along its top row from left (darkest tone) to right (brightest). |
| `reverse` | BOOLEAN | False |  | Read the gradient right to left. |
| `mode` | COMBO | MATTE | menu: `MATTE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | Resize of the result. MATTE = keep its size; FIT = stretch to wh; CROP = fill wh and trim; ASPECT = scale keeping proportions. |
| `wh` | VEC2 | (512, 512) | 32 to | Target width and height when mode is not MATTE. |
| `sample` | COMBO | LANCZOS4 | menu: `NEAREST`, `LINEAR`, `CUBIC`, `AREA`, `LANCZOS4`, `LINEAR_EXACT`, `NEAREST_EXACT` | Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = hard pixels. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

## COMPOSE

<details>
<summary><b>BLEND ⚗️</b> &nbsp; <code>BLEND (JOV) ⚗️</code></summary>

Layer a foreground over a background with one of thirty blend modes, such as multiply, screen or overlay, through an optional mask. The workhorse for compositing.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `back` | IMAGE, MASK |  |  | Background picture. Sets the size unless mode resizes. |
| `fore` | IMAGE, MASK |  |  | Foreground picture, centred on the background. |
| `mask` | IMAGE, MASK |  |  | Where the foreground shows: white shows it, black hides it. When empty, the foreground's own alpha is used. |
| `func` | COMBO | NORMAL | menu of 30 | Blend mode. NORMAL = place on top; MULTIPLY = darken; SCREEN = lighten; OVERLAY = contrast; DIFFERENCE = compare two pictures. |
| `alpha` | FLOAT | 1 | 0 to 1 | Opacity of the foreground. 0 = background only; 1 = full blend. |
| `swap` | BOOLEAN | False |  | Exchange background and foreground. |
| `invert` | BOOLEAN | False |  | Invert the mask, so the foreground shows where it was black. |
| `mode` | COMBO | MATTE | menu: `MATTE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | Resize of the result. MATTE = keep its size; FIT = stretch to wh; CROP = fill wh and trim; ASPECT = scale keeping proportions; RESIZE_MATTE = pad or trim to wh. |
| `wh` | VEC2 | (512, 512) | 32 to | Target width and height when mode is not MATTE. |
| `sample` | COMBO | LANCZOS4 | menu: `NEAREST`, `LINEAR`, `CUBIC`, `AREA`, `LANCZOS4`, `LINEAR_EXACT`, `NEAREST_EXACT` | Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = hard pixels. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |
| `input` | COMBO | NONE | menu: `NONE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | Fit the inputs to each other before blending. NONE = centre them as they are; FIT, CROP and ASPECT size both to the larger one. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>FILTER MASK 🤿</b> &nbsp; <code>FILTER MASK (JOV) 🤿</code></summary>

Make a mask from the pixels close to one colour, or between two colours. Use it to key out a background or isolate one colour for adjustment.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture: RGBA, RGB or a mask. A batch is processed frame by frame. |
| `start` | VEC3 | (128, 128, 128) | colour, 0 to 255 | The colour to keep, RGB 0 to 255; with range on, the low end. |
| `range` | BOOLEAN | False |  | Keep every colour between start and end rather than only those near start. |
| `end` | VEC3 | (128, 128, 128) | colour, 0 to 255 | The high end of the colour range, used when range is on. |
| `fuzz` | VEC3 | (0.5, 0.5, 0.5) | 0 to 1 | Tolerance per channel, 0 to 1, added on both sides. 0 = exact colour only; 0.1 = close shades; 0.5 = half the range. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>HISTOGRAM</b> &nbsp; <code>HISTOGRAM (JOV)</code></summary>

Draw a picture's brightness histogram: how many pixels sit at each level from black on the left to white on the right. Shows clipping and contrast at a glance.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture: RGBA, RGB or a mask. A batch is processed frame by frame. |
| `wh` | VEC2 | (512, 512) | 32 to | Width and height of the histogram picture. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>PIXEL MERGE 🫂</b> &nbsp; <code>PIXEL MERGE (JOV) 🫂</code></summary>

Build a picture from separate red, green, blue and alpha planes, filling any missing plane from a base picture or the matte. The partner of PIXEL SPLIT, for channel packing.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | Base picture whose channels fill any plane not connected. |
| `❤️` | IMAGE, MASK |  |  | Red channel plane. |
| `💚` | IMAGE, MASK |  |  | Green channel plane. |
| `💙` | IMAGE, MASK |  |  | Blue channel plane. |
| `🤍` | IMAGE, MASK |  |  | Alpha channel plane. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Level used for a channel with no plane and no base picture, RGBA 0 to 255. |
| `flip` | VEC4 | (0, 0, 0, 0) | 0 to 1 | How far to invert each plane before merging, R, G, B, A, 0 to 1. 0 = as is; 1 = fully inverted. |
| `invert` | BOOLEAN | False |  | Invert the colour of the merged picture, alpha kept. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>PIXEL SPLIT 💔</b> &nbsp; <code>PIXEL SPLIT (JOV) 💔</code></summary>

Split a picture into its red, green, blue and alpha channels as masks, plus its RGB. Edit channels separately and rebuild them with PIXEL MERGE.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture: RGBA, RGB or a mask. A batch is processed frame by frame. |

| Output | Type | Description |
|---|---|---|
| `❤️` | MASK list | The red channel as a mask. |
| `💚` | MASK list | The green channel as a mask. |
| `💙` | MASK list | The blue channel as a mask. |
| `🤍` | MASK list | The alpha channel as a mask; white when the picture has no alpha. |
| `RGB` | IMAGE list | The picture without its alpha. |

</details>

<details>
<summary><b>PIXEL SWAP 🔃</b> &nbsp; <code>PIXEL SWAP (JOV) 🔃</code></summary>

Build a picture whose red, green, blue and alpha each come from any channel of picture A, picture B or a constant. Swap channels or move a mask into alpha.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `source` | IMAGE, MASK |  |  | Picture A. Sets the size of the result. |
| `target` | IMAGE, MASK |  |  | Picture B, fitted to A's size. |
| `swap r` | COMBO | RED_A | menu: `RED_A`, `GREEN_A`, `BLUE_A`, `ALPHA_A`, `RED_B`, `GREEN_B`, `BLUE_B`, `ALPHA_B`, `CONSTANT` | Source of red: a channel of A (_A) or B (_B), or CONSTANT from matte. |
| `swap g` | COMBO | GREEN_A | menu: `RED_A`, `GREEN_A`, `BLUE_A`, `ALPHA_A`, `RED_B`, `GREEN_B`, `BLUE_B`, `ALPHA_B`, `CONSTANT` | Source of green. |
| `swap b` | COMBO | BLUE_A | menu: `RED_A`, `GREEN_A`, `BLUE_A`, `ALPHA_A`, `RED_B`, `GREEN_B`, `BLUE_B`, `ALPHA_B`, `CONSTANT` | Source of blue. |
| `swap a` | COMBO | ALPHA_A | menu: `RED_A`, `GREEN_A`, `BLUE_A`, `ALPHA_A`, `RED_B`, `GREEN_B`, `BLUE_B`, `ALPHA_B`, `CONSTANT` | Source of alpha. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Constant for each channel set to CONSTANT, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>THRESHOLD 📉</b> &nbsp; <code>THRESHOLD (JOV) 📉</code></summary>

Cut a picture into light and dark at a threshold, either one level for the whole picture or one adapted to each neighbourhood. Good for masks, scans and line extraction.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture: RGBA, RGB or a mask. A batch is processed frame by frame. |
| `adapt` | COMBO | ADAPT_NONE | menu: `ADAPT_NONE`, `ADAPT_MEAN`, `ADAPT_GAUSS` | ADAPT_NONE = one threshold everywhere; ADAPT_MEAN and ADAPT_GAUSS = each pixel against its neighbourhood, for uneven lighting. |
| `func` | COMBO | BINARY | menu: `BINARY`, `TRUNC`, `TOZERO` | BINARY = white above, black below; TRUNC = cap values at the threshold; TOZERO = black below, unchanged above. |
| `threshold` | FLOAT | 0.5 | 0 to 1 | The cut level, 0 to 1, for ADAPT_NONE. |
| `size` | INT | 3 | 3 to 103 | Neighbourhood size in pixels for the adaptive modes, raised to the next odd number. |
| `invert` | BOOLEAN | False |  | Invert the result. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

## CREATE

<details>
<summary><b>CONSTANT 🟪</b> &nbsp; <code>CONSTANT (JOV) 🟪</code></summary>

Make a solid colour picture of any size, or place a picture over a colour through its alpha or a mask. Backgrounds, mattes and colour cards.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | Optional picture laid over the colour. It sets the size when mode is MATTE. |
| `mask` | IMAGE, MASK |  |  | Replaces the picture's alpha: black shows the picture, white shows the colour. |
| `color` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | The colour, RGBA 0 to 255. |
| `mode` | COMBO | MATTE | menu: `MATTE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | MATTE = the picture's size, or wh with no picture; FIT, CROP and ASPECT resize the result to wh. |
| `wh` | VEC2 | (512, 512) | 1 to | Width and height of the canvas. |
| `sample` | COMBO | LANCZOS4 | menu: `NEAREST`, `LINEAR`, `CUBIC`, `AREA`, `LANCZOS4`, `LINEAR_EXACT`, `NEAREST_EXACT` | Resampling filter when resizing. LANCZOS4 = sharpest; NEAREST = hard pixels. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>SHAPE GEN ✨</b> &nbsp; <code>SHAPE GEN (JOV) ✨</code></summary>

Draw a circle, square or regular polygon of any size, position, angle and softness. Its MASK output makes a ready-made shape mask.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `shape` | COMBO | CIRCLE | menu: `CIRCLE`, `SQUARE`, `POLYGON` | CIRCLE, SQUARE or POLYGON. size stretches the circle and square into an ellipse and a rectangle. |
| `sides` | INT | 3 | 3 to 100 | Number of sides of the POLYGON. 3 = triangle; 6 = hexagon. |
| `color` | VEC4 | (255, 255, 255, 255) | colour, 0 to 255 | Colour of the shape, RGBA 0 to 255. Alpha sets its opacity. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Background colour, RGB 0 to 255. |
| `wh` | VEC2 | (256, 256) | 32 to | Width and height of the canvas. |
| `xy` | VEC2 | (0, 0) | -1 to 1 | Offset of the shape, -1 to 1 of the canvas. (0, 0) = centred. |
| `angle` | FLOAT | 0 | -180 to 180 | Rotation in degrees, clockwise. |
| `size` | VEC2 | (1, 1) | 0 to 1 | Size of the shape as a share of the canvas, 0 to 1. (1, 1) = as large as fits. |
| `edge` | COMBO | CLIP | menu: `CLIP`, `WRAP`, `WRAPX`, `WRAPY` | What happens past the canvas edge. CLIP = cut off; WRAP = reappear on the other side. |
| `blur` | FLOAT | 0 | 0 to 1024 | Softness of the edge, in pixels. 0 = hard edge. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>TEXT GEN 📝</b> &nbsp; <code>TEXT GEN (JOV) 📝</code></summary>

Render text into a picture with any installed font, aligned, justified, rotated and optionally sized to fit. Letter mode makes one picture per character, for animated titles.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `string` | STRING | jovimetrix |  | The text to draw. Each line break starts a new line. |
| `font` | COMBO | Arial | menu of 535 | Font family, from the fonts installed on this machine. 'default' is the built-in font; a font missing here falls back to the default. |
| `letter` | BOOLEAN | False |  | Draw each character as its own picture, as a batch. |
| `autosize` | BOOLEAN | False |  | Size the text to fill wh, ignoring size. |
| `color` | VEC4 | (255, 255, 255, 255) | colour, 0 to 255 | Colour of the letters, RGBA 0 to 255. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Background colour, RGBA 0 to 255. |
| `cols` | INT | 0 | 0 to 1000 | With autosize, wrap lines at this many characters. 0 = no wrap. |
| `size` | INT | 16 | 8 to 2048 | Font size. Ignored when autosize is on. |
| `align` | COMBO | CENTER | menu: `TOP`, `CENTER`, `BOTTOM` | Vertical placement: TOP, CENTER or BOTTOM. |
| `justify` | COMBO | CENTER | menu: `LEFT`, `CENTER`, `RIGHT` | Horizontal placement of each line: LEFT, CENTER or RIGHT. |
| `margin` | INT | 0 | -1024 to 1024 | Space kept from the canvas edges, in pixels. |
| `spacing` | INT | 0 | -1024 to 1024 | Extra space between lines, in pixels. |
| `wh` | VEC2 | (256, 256) | 32 to | Width and height of the canvas. |
| `xy` | VEC2 | (0, 0) | -1 to 1 | Offset of the text, -1 to 1 of the canvas. |
| `angle` | FLOAT | 0 |  | Rotation in degrees, clockwise. |
| `edge` | COMBO | CLIP | menu: `CLIP`, `WRAP`, `WRAPX`, `WRAPY` | What happens past the canvas edge. CLIP = cut off; WRAP = reappear on the other side. |
| `invert` | BOOLEAN | False |  | Invert the colours of the result. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

## TRANSFORM

<details>
<summary><b>CROP ✂️</b> &nbsp; <code>CROP (JOV) ✂️</code></summary>

Cut a region out of a picture: a centred window, a window at a position, or any four-cornered shape. Pulls a region of interest out of a frame.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to crop. |
| `func` | COMBO | CENTER | menu: `CENTER`, `XY`, `FREE` | CENTER = a wh window from the middle; XY = a wh window whose top-left corner is at xy; FREE = the shape inside the four corners. |
| `xy` | VEC2 | (0, 0) | 0 to 1 | XY mode: top-left corner of the window. 0 to 1 is a share of the picture; above 1 is pixels. |
| `wh` | VEC2 | (512, 512) | 32 to | Width and height of the window, in pixels. |
| `tl-tr` | VEC4 | (0, 0, 0, 1) | 0 to 1 | FREE mode: x, y of the first corner, then x, y of the second, each 0 to 1 of the picture. |
| `bl-br` | VEC4 | (1, 0, 1, 1) | 0 to 1 | FREE mode: x, y of the fourth corner, then x, y of the third. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>FLATTEN ⬇️</b> &nbsp; <code>FLATTEN (JOV) ⬇️</code></summary>

Add every picture wired into its growing image inputs, and every frame of each batch, into one picture. A quick slap comp of layers or masks.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `mode` | COMBO | MATTE | menu: `MATTE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | Resize of the result. MATTE = keep its size; FIT = stretch to wh; CROP = fill wh and trim; ASPECT = scale keeping proportions; RESIZE_MATTE = pad or trim to wh. |
| `wh` | VEC2 | (512, 512) | 1 to | Canvas width and height when mode is not MATTE. MATTE uses the largest input. |
| `sample` | COMBO | LANCZOS4 | menu: `NEAREST`, `LINEAR`, `CUBIC`, `AREA`, `LANCZOS4`, `LINEAR_EXACT`, `NEAREST_EXACT` | Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = hard pixels. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |
| `offset` | VEC2 | (0, 0) | 0 to | Shift every layer by this many pixels before adding. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>SPLIT 🎭</b> &nbsp; <code>SPLIT (JOV) 🎭</code></summary>

Cut a picture in two at a chosen point, top and bottom or left and right. Separates a side-by-side pair or a stacked comparison.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to split. |
| `value` | FLOAT | 0.5 | 0 to 1 | Where to cut, 0 to 1 of the picture. 0.5 = in half. |
| `flip` | BOOLEAN | False |  | Off = cut across into top and bottom; on = cut down into left and right. |
| `mode` | COMBO | MATTE | menu: `MATTE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | Resize of the result. MATTE = keep its size; FIT = stretch to wh; CROP = fill wh and trim; ASPECT = scale keeping proportions; RESIZE_MATTE = pad or trim to wh. |
| `wh` | VEC2 | (512, 512) | 32 to | Size each half is fitted to when mode is not MATTE. |
| `sample` | COMBO | LANCZOS4 | menu: `NEAREST`, `LINEAR`, `CUBIC`, `AREA`, `LANCZOS4`, `LINEAR_EXACT`, `NEAREST_EXACT` | Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = hard pixels. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `IMAGEA` | IMAGE list | The top or left part. |
| `IMAGEB` | IMAGE list | The bottom or right part. |

</details>

<details>
<summary><b>STACK ➕</b> &nbsp; <code>STACK (JOV) ➕</code></summary>

Place every picture wired into its growing image inputs, and every frame of each batch, in a row, a column or a grid. Contact sheets and side-by-side comparisons.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `axis` | COMBO | GRID | menu: `HORIZONTAL`, `VERTICAL`, `GRID` | HORIZONTAL = one row; VERTICAL = one column; GRID = rows of step pictures. |
| `step` | INT | 1 | 0 to 4096 | GRID only: pictures per row. 0 = as square as possible. |
| `mode` | COMBO | MATTE | menu: `MATTE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | Resize of the result. MATTE = keep its size; FIT = stretch to wh; CROP = fill wh and trim; ASPECT = scale keeping proportions; RESIZE_MATTE = pad or trim to wh. |
| `wh` | VEC2 | (512, 512) | 32 to | Size the result is fitted to when mode is not MATTE. |
| `sample` | COMBO | LANCZOS4 | menu: `NEAREST`, `LINEAR`, `CUBIC`, `AREA`, `LANCZOS4`, `LINEAR_EXACT`, `NEAREST_EXACT` | Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = hard pixels. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

<details>
<summary><b>TRANSFORM 🏝️</b> &nbsp; <code>TRANSFORM (JOV) 🏝️</code></summary>

Move, rotate, scale, tile and mirror a picture, then optionally project it through a perspective, sphere, fisheye or polar warp.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture to transform. |
| `mask` | IMAGE, MASK |  |  | Replaces the picture's alpha before transforming. |
| `xy` | VEC2 | (0, 0) | -1 to 1 | Move, -1 to 1 of the picture. (0.5, 0) = half a width right. |
| `angle` | FLOAT | 0 |  | Rotation in degrees, clockwise. |
| `size` | VEC2 | (1, 1) | 0.001 to | Scale on each axis. 1 = unchanged; 2 = double; negative mirrors. |
| `tile` | VEC2 | (1, 1) | 1 to | Repeat the picture this many times across and down. 1 = once. |
| `edge` | COMBO | CLIP | menu: `CLIP`, `WRAP`, `WRAPX`, `WRAPY` | What fills the space a move or rotation uncovers. CLIP = empty; WRAP = the opposite edge; WRAPX, WRAPY = one axis. |
| `mirror` | COMBO | NONE | menu: `NONE`, `X`, `FLIP_X`, `Y`, `FLIP_Y`, `XY`, `X_FLIP_Y`, `FLIP_XY`, `FLIP_X_FLIP_Y` | Mirror one half onto the other across the pivot. X = left onto right; Y = top onto bottom; FLIP_ = the other half. |
| `pivot` | VEC2 | (0.5, 0.5) | 0 to 1 | Where the mirror line sits, 0 to 1 of the picture. |
| `proj` | COMBO | NORMAL | menu: `NORMAL`, `POLAR`, `SPHERICAL`, `FISHEYE`, `PERSPECTIVE` | Projection after the transform. PERSPECTIVE uses the four corners; SPHERICAL and FISHEYE use strength; POLAR wraps into a circle. |
| `tl-tr` | VEC4 | (0, 0, 1, 0) | 0 to 1 | PERSPECTIVE: where the top-left and top-right corners land, x, y pairs 0 to 1. |
| `bl-br` | VEC4 | (0, 1, 1, 1) | 0 to 1 | PERSPECTIVE: where the bottom-left and bottom-right corners land, x, y pairs 0 to 1. |
| `strength` | FLOAT | 1 | 0 to 1 | SPHERICAL and FISHEYE amount. 0 = flat; 1 = full. |
| `mode` | COMBO | MATTE | menu: `MATTE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | Resize of the result. MATTE = keep its size; FIT = stretch to wh; CROP = fill wh and trim; ASPECT = scale keeping proportions; RESIZE_MATTE = pad or trim to wh. |
| `wh` | VEC2 | (512, 512) | 32 to | Size the result is fitted to when mode is not MATTE. |
| `sample` | COMBO | LANCZOS4 | menu: `NEAREST`, `LINEAR`, `CUBIC`, `AREA`, `LANCZOS4`, `LINEAR_EXACT`, `NEAREST_EXACT` | Resampling filter. LANCZOS4 = sharpest; LINEAR = soft; NEAREST = hard pixels. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around a resized picture, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE list | The picture with its alpha channel. Where there is alpha, it masks the picture. |
| `RGB` | IMAGE list | The picture as three colour channels, with no alpha. |
| `MASK` | MASK list | The alpha channel as a mask: white where the picture is opaque. |

</details>

## UTILITY/BATCH

<details>
<summary><b>ARRAY 📚</b> &nbsp; <code>ARRAY (JOV) 📚</code></summary>

Gather everything wired into its growing inputs, batches split into frames, into one list, then keep all of it, one entry, a slice, chosen indices or a random sample. Pictures come out as one batch.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `mode` | COMBO | MERGE | menu: `MERGE`, `PICK`, `SLICE`, `INDEX_LIST`, `RANDOM` | MERGE = everything; PICK = the entry at range start; SLICE = start to end by step; INDEX_LIST = the indices typed in index; RANDOM = a random sample. |
| `range` | VEC3 | (0, 0, 1) | 0 to | Start, end and step for PICK and SLICE. End 0 = to the last entry; a negative step reverses. |
| `index` | STRING |  |  | INDEX_LIST: comma separated indices and ranges, counted from 0. Example: 0,2,5-8 |
| `count` | INT | 0 | 0 to | Keep at most this many entries. 0 = all; for RANDOM, the sample size. |
| `reverse` | BOOLEAN | False |  | Reverse the order of the result. |
| `seed` | INT | 0 | 0 to | Seed for RANDOM. The same seed picks the same sample. |

| Output | Type | Description |
|---|---|---|
| `ARRAY` | * list | The resulting entries. Pictures arrive one per run downstream; other values as one list. |
| `LENGTH` | INT list | How many entries the result holds. |

</details>

<details>
<summary><b>BATCH TO LIST</b> &nbsp; <code>BATCH TO LIST (JOV)</code></summary>

Turn a batch of pictures, masks or latents, or a Python list, into a list, so the next node runs once per entry instead of once for the batch.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `batch` | * |  |  | A picture, mask or latent batch, or a list of values. |

| Output | Type | Description |
|---|---|---|
| `LIST` | * list | One entry per frame of the batch, each a batch of one. |

</details>

<details>
<summary><b>QUEUE TOO 🗃</b> &nbsp; <code>QUEUE TOO (JOV) 🗃</code></summary>

Step through a list of pictures, one per run, handing each on as RGBA, RGB and mask, optionally resized. Each run steps to the next entry; select jumps, hold pauses, and reset starts over.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `queue` | STRING | ./res/img/test-a.png |  | One entry per line: a value, a file, a folder, a .txt list, or a folder with patterns. Example: input/frames;*.png;*.jpg |
| `recurse` | BOOLEAN | False |  | Also search the folders inside each folder listed. |
| `batch` | BOOLEAN | False |  | Load every entry at once as one batch instead of one entry per run. |
| `select` | INT | 0 | 0 to | Jump to this entry, counted from 1. 0 = step to the next entry each run. |
| `hold` | BOOLEAN | False |  | Stay on the current entry instead of stepping. |
| `stop` | BOOLEAN | False |  | When the list runs out, stop the run instead of carrying on. |
| `loop` | BOOLEAN | True |  | Start over at the first entry after the last. Off = stay on the last. |
| `reset` | BOOLEAN | False |  | Go back to the first entry and read the list again on the next run. |
| `mode` | COMBO | MATTE | menu: `MATTE`, `CROP`, `FIT`, `ASPECT`, `ASPECT_SHORT`, `RESIZE_MATTE` | Resize of each picture. MATTE = as loaded, or padded to the largest in batch mode; FIT, CROP, ASPECT = to wh. |
| `wh` | VEC2 | (512, 512) | 32 to | Target width and height when mode is not MATTE. |
| `sample` | COMBO | LANCZOS4 | menu: `NEAREST`, `LINEAR`, `CUBIC`, `AREA`, `LANCZOS4`, `LINEAR_EXACT`, `NEAREST_EXACT` | Resampling filter. LANCZOS4 = sharpest; NEAREST = hard pixels. |
| `matte` | VEC4 | (0, 0, 0, 255) | colour, 0 to 255 | Colour behind transparent areas and around resized pictures, RGBA 0 to 255. |

| Output | Type | Description |
|---|---|---|
| `RGBA` | IMAGE | The picture with its alpha. |
| `RGB` | IMAGE | The picture without alpha. |
| `MASK` | MASK | The picture's alpha as a mask. |
| `CURRENT` | STRING | The current file path. |
| `INDEX` | INT | Position of the current entry, counted from 1. |
| `TOTAL` | INT | How many entries the list holds. |
| `TRIGGER` | BOOLEAN | True on the run that reaches the end of the list. |

</details>

<details>
<summary><b>QUEUE 🗃</b> &nbsp; <code>QUEUE (JOV) 🗃</code></summary>

Step through a list of values, files or folders, one entry per run. Pictures and JSON files are loaded; anything else passes through as text or a number. Each run steps to the next entry; select jumps, hold pauses, and reset starts over.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `queue` | STRING | ./res/img/test-a.png |  | One entry per line: a value, a file, a folder, a .txt list, or a folder with patterns. Example: input/frames;*.png;*.jpg |
| `recurse` | BOOLEAN | False |  | Also search the folders inside each folder listed. |
| `batch` | BOOLEAN | False |  | Load every entry at once as one batch instead of one entry per run. |
| `select` | INT | 0 | 0 to | Jump to this entry, counted from 1. 0 = step to the next entry each run. |
| `hold` | BOOLEAN | False |  | Stay on the current entry instead of stepping. |
| `stop` | BOOLEAN | False |  | When the list runs out, stop the run instead of carrying on. |
| `loop` | BOOLEAN | True |  | Start over at the first entry after the last. Off = stay on the last. |
| `reset` | BOOLEAN | False |  | Go back to the first entry and read the list again on the next run. |

| Output | Type | Description |
|---|---|---|
| `❔` | * | The current entry, loaded: a picture, JSON data, text or a number. |
| `QUEUE` | * | The whole list of entries. |
| `CURRENT` | STRING | The current entry as text, such as its file path. |
| `INDEX` | INT | Position of the current entry, counted from 1. |
| `TOTAL` | INT | How many entries the list holds. |
| `TRIGGER` | BOOLEAN | True on the run that reaches the end of the list. |

</details>

## UTILITY/INFO

<details>
<summary><b>AKASHIC 📓</b> &nbsp; <code>AKASHIC (JOV) 📓</code></summary>

Show anything wired into its growing inputs as text on the node: numbers, text, lists, and the shape of pictures, masks and latents. A quick look inside a graph.

</details>

<details>
<summary><b>GRAPH 📈</b> &nbsp; <code>GRAPH (JOV) 📈</code></summary>

Plot the numbers wired into its growing inputs as lines that grow with every run. Watch a value change across an animation or a seed sweep.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `reset` | BOOLEAN | False |  | Clear the history before plotting this run. |
| `value` | INT | 60 | 0 to 100000 | How many recent values each line shows. 0 = all, up to 100000. |
| `wh` | VEC2 | (512, 512) | 32 to | Width and height of the graph picture. |

| Output | Type | Description |
|---|---|---|
| `IMAGE` | IMAGE | The graph. |

</details>

<details>
<summary><b>IMAGE INFO 📚</b> &nbsp; <code>IMAGE INFO (JOV) 📚</code></summary>

Read a picture's batch count, width, height and channel count, singly and as vectors. Size other nodes to match an input.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The picture or mask to measure. |

| Output | Type | Description |
|---|---|---|
| `COUNT` | INT | Number of frames in the batch. |
| `W` | INT | Width in pixels. |
| `H` | INT | Height in pixels. |
| `C` | INT | Channels: 1 = mask, 3 = RGB, 4 = RGBA. |
| `WH` | VEC2 | Width and height as a VEC2. |
| `WHC` | VEC3 | Width, height and channels as a VEC3. |

</details>

## UTILITY/IO

<details>
<summary><b>DELAY ✋🏽</b> &nbsp; <code>DELAY (JOV) ✋🏽</code></summary>

Pause the run for a set time, then pass its input on. A pause of more than a few seconds shows a prompt to continue now or cancel the run.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `in` | * |  |  | The value held until the pause ends, then passed to OUT. |
| `timer` | INT | 0 | -1 to 10000000 | Seconds to wait. 0 = no pause; -1 = wait until continued or cancelled, up to the configured maximum. |
| `enable` | BOOLEAN | True |  | Show floating bubbles on the canvas while the prompt is up. |

| Output | Type | Description |
|---|---|---|
| `OUT` | * list | The input, passed on unchanged when the pause ends. |

</details>

<details>
<summary><b>EXPORT 📽</b> &nbsp; <code>EXPORT (JOV) 📽</code></summary>

Save a batch of pictures as numbered PNG or JPG files, or as one animated GIF, into ComfyUI's output folder or a folder below it.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE, MASK |  |  | The pictures to save, one file or frame each. |
| `path` | STRING |  |  | Folder to save into. Empty = ComfyUI's output folder; a relative path such as 'renders/shot1' is placed below it. |
| `format` | COMBO | gif | menu: `gif`, `png`, `jpg`, `gifski` | gif = one animated GIF; png and jpg = one file per picture. gifski is kept so older workflows open and writes the same GIF as gif. |
| `prefix` | STRING | jovi |  | File name without extension. Example: 'shot' gives shot.gif, then shot_1.gif. |
| `overwrite` | BOOLEAN | False |  | Replace a file of the same name. Off = add a number instead. |
| `opt` | BOOLEAN | False |  | gif and png: spend longer making the file smaller. |
| `quality` | INT | 90 | 1 to 100 | jpg: picture quality. 100 = best, largest files. |
| `motion` | INT | 100 | 1 to 100 | Not used. Kept so older workflows open; it set the gifski program's motion quality. |
| `fps` | INT | 24 | 1 to 60 | gif: frames per second. |
| `loop` | INT | 0 | 0 to 65535 | gif: how many times the animation repeats. 0 = forever. |

</details>

<details>
<summary><b>ROUTE 🚌</b> &nbsp; <code>ROUTE (JOV) 🚌</code></summary>

Pass up to ten values of any type through one node, each to the output beside its input. Tidies long links across a large graph.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `route` | BUS |  |  | Another ROUTE's ROUTE output, passed straight on. |

| Output | Type | Description |
|---|---|---|
| `ROUTE` | BUS | The incoming route, passed on. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |
| `🔮` | * list | The value wired into the matching input. |

</details>

<details>
<summary><b>SAVE OUTPUT 💾</b> &nbsp; <code>SAVE OUTPUT (JOV) 💾</code></summary>

Save pictures as PNG files with a name you choose, carrying the workflow and any extra metadata you add, into ComfyUI's output folder or a folder below it.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `image` | IMAGE |  |  | The pictures to save. |
| `path` | STRING |  |  | Folder to save into. Empty = ComfyUI's output folder; a relative path such as 'renders' is placed below it. |
| `name` | STRING | output |  | File name without extension. Several pictures add _0, _1, and so on. |
| `meta` | JSON |  |  | Extra metadata as a dictionary, written into the file. |
| `user` | STRING |  |  | Extra metadata typed as JSON. Example: {"artist": "me"} |
| `overwrite` | BOOLEAN | False |  | Replace a file of the same name. Off = add a number instead. |

</details>

## VARIABLE

<details>
<summary><b>VALUE 🧬</b> &nbsp; <code>VALUE (JOV) 🧬</code></summary>

Supply a boolean, integer, float or vector, typed in or converted from whatever is wired in, with its components on separate outputs. With a seed it picks a random value between aa and bb.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `a` | * |  |  | A value to convert to the chosen type. When empty, aa is used. |
| `x` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Overrides the X of aa. |
| `y` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Overrides the Y of aa. |
| `z` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Overrides the Z of aa. |
| `w` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Overrides the W of aa. |
| `type` | COMBO | BOOLEAN | menu: `BOOLEAN`, `INT`, `FLOAT`, `VEC2`, `VEC3`, `VEC4` | Type of the value: BOOLEAN, INT, FLOAT, or a VEC2 to VEC4 vector. |
| `aa` | VEC4 | (0, 0, 0, 0) |  | The value. With a seed, the low end of the random range. |
| `bb` | VEC4 | (1, 1, 1, 1) |  | With a seed, the high end of the random range. Otherwise unused. |
| `seed` | INT | 0 | 0 to | 0 = no randomising. Any other value picks a random value between aa and bb per component; the same seed repeats it. |

| Output | Type | Description |
|---|---|---|
| `❔` | * list | The value, of the chosen type. |
| `x` | * list | The X component. |
| `y` | * list | The Y component. |
| `z` | * list | The Z component. |
| `w` | * list | The W component. |

</details>

<details>
<summary><b>VECTOR2</b> &nbsp; <code>VECTOR2 (JOV)</code></summary>

Build a two component float vector, such as a size or a position, from typed values or wired numbers.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `x` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | X component. Overrides the X of default when wired. |
| `y` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Y component. Overrides the Y of default when wired. |
| `default` | VEC2 | (0, 0) |  | Typed vector used for any component not wired in. |

| Output | Type | Description |
|---|---|---|
| `VEC2` | VEC2 list | The two component vector. |

</details>

<details>
<summary><b>VECTOR3</b> &nbsp; <code>VECTOR3 (JOV)</code></summary>

Build a three component float vector, such as an RGB colour or a 3D position, from typed values or wired numbers.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `x` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | X component. Overrides the X of default when wired. |
| `y` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Y component. Overrides the Y of default when wired. |
| `z` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Z component. Overrides the Z of default when wired. |
| `default` | VEC3 | (0, 0, 0) |  | Typed vector used for any component not wired in. |

| Output | Type | Description |
|---|---|---|
| `VEC3` | VEC3 list | The three component vector. |

</details>

<details>
<summary><b>VECTOR4</b> &nbsp; <code>VECTOR4 (JOV)</code></summary>

Build a four component float vector, such as an RGBA colour or a rectangle, from typed values or wired numbers.

| Input | Type | Default | Range or options | Description |
|---|---|---|---|---|
| `x` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | X component. Overrides the X of default when wired. |
| `y` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Y component. Overrides the Y of default when wired. |
| `z` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | Z component. Overrides the Z of default when wired. |
| `w` | BOOLEAN, FLOAT, INT, VEC2, VEC3, VEC4 |  |  | W component. Overrides the W of default when wired. |
| `default` | VEC4 | (0, 0, 0, 0) |  | Typed vector used for any component not wired in. |

| Output | Type | Description |
|---|---|---|
| `VEC4` | VEC4 list | The four component vector. |

</details>
