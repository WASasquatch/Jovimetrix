# Jovimetrix features

What the pack does, by area. Every node's inputs and outputs are in [NODES.md](NODES.md).

[docs/workflows/jovimetrix-tour.json](docs/workflows/jovimetrix-tour.json) is a graph to open and
run: shapes, text and blending; adjusting and colouring a picture that ships with the pack; and
animated values plotted over a run. It needs no models and no files of its own.

## Pictures in, pictures out

Every picture input takes RGBA, RGB or a mask, and every picture node hands back three outputs:
`RGBA`, `RGB` and `MASK`. A batch is processed frame by frame, and a list of settings wired into
any input runs the node once per entry.

## Adjust

- **ADJUST: BLUR, SHARPEN, EMBOSS** soften, sharpen or relief a picture.
  [ADJUST](NODES.md#adjust)
- **ADJUST: LIGHT and LEVELS** set brightness, contrast, exposure and gamma, or black, mid and
  white points by hand or automatically. [ADJUST](NODES.md#adjust)
- **ADJUST: COLOR** shifts the channels in RGB, HSV, YUV, LAB, LUV or XYZ, for hue rotations and
  tints. [ADJUST](NODES.md#adjust)
- **ADJUST: EDGE and MORPHOLOGY** find edges and grow, shrink, open or close shapes, for line art
  and mask clean-up. [ADJUST](NODES.md#adjust)
- **ADJUST: PIXEL** pixelates, rescales, quantises or posterises, for retro looks.
  [ADJUST](NODES.md#adjust)

## Color

- **COLOR MATCH** moves one picture's colours onto another, or maps its tones through a colour
  table, to keep a sequence in one grade. [COLOR](NODES.md#color)
- **COLOR MEANS** finds a picture's dominant colours and hands them on as swatches, a palette, a
  gradient and a 3D LUT. [COLOR](NODES.md#color)
- **COLOR THEORY** builds complementary, triadic, analogous and other harmonies from a picture's
  average colour. [COLOR](NODES.md#color)
- **GRADIENT MAP** recolours a picture's tones through any gradient picture, for duotones and heat
  maps. [COLOR](NODES.md#color)
- **COLOR BLIND** shows how a picture reads with red, green or blue colour blindness.
  [COLOR](NODES.md#color)

## Compose

- **BLEND** layers one picture over another with thirty blend modes through an optional mask.
  [COMPOSE](NODES.md#compose)
- **PIXEL SPLIT, PIXEL MERGE and PIXEL SWAP** pull channels apart, rebuild them, and move any
  channel of one picture into another. [COMPOSE](NODES.md#compose)
- **FILTER MASK and THRESHOLD** make masks from a colour range or a brightness cut.
  [COMPOSE](NODES.md#compose)
- **HISTOGRAM** draws a picture's brightness histogram. [COMPOSE](NODES.md#compose)

## Create

- **CONSTANT** makes solid colour canvases and mattes. [CREATE](NODES.md#create)
- **SHAPE GEN** draws circles, rectangles and regular polygons with soft edges, and their masks.
  [CREATE](NODES.md#create)
- **TEXT GEN** renders text in any installed font, sized to fit if asked, or one picture per
  letter for animated titles. [CREATE](NODES.md#create)

## Transform

- **TRANSFORM** moves, rotates, scales, tiles and mirrors a picture, then optionally projects it
  through a perspective, sphere, fisheye or polar warp. [TRANSFORM](NODES.md#transform)
- **CROP and SPLIT** cut out a region, or cut a picture in two. [TRANSFORM](NODES.md#transform)
- **STACK and FLATTEN** lay many pictures out in a row, column or grid, or add them into one.
  [TRANSFORM](NODES.md#transform)

## Values and maths

- **VALUE, VECTOR2, VECTOR3 and VECTOR4** supply typed numbers and vectors, and convert between
  boolean, integer, float and vector. VALUE can also pick a seeded random value in a range.
  [VARIABLE](NODES.md#variable)
- **OP UNARY and OP BINARY** apply arithmetic, trigonometry, logic, bitwise and set operations to
  numbers, vectors and pictures. [CALC](NODES.md#calc)
- **LERP, SWIZZLE, COMPARISON and BIT SPLIT** blend values, rearrange vector components, switch
  on a test and split values into bits. [CALC](NODES.md#calc)
- **STRINGER** splits, joins, filters, replaces and slices text. [CALC](NODES.md#calc)

## Animation

- **TICK** generates a frame series with looping, ping-pong, normalising and thirty easing curves.
  [ANIMATION](NODES.md#animation)
- **WAVE GEN** samples sine, square, sawtooth, noise and other waveforms over time.
  [ANIMATION](NODES.md#animation)

## Lists, queues and inspection

- **ARRAY and BATCH TO LIST** gather, pick, slice, index and sample values and batches.
  [UTILITY/BATCH](NODES.md#utilitybatch)
- **QUEUE and QUEUE TOO** step through values, files and folders, one entry per run, or load a
  whole folder of pictures as one batch. [UTILITY/BATCH](NODES.md#utilitybatch)
- **AKASHIC, GRAPH and IMAGE INFO** show any value on the node, plot values across runs and read
  a picture's size. [UTILITY/INFO](NODES.md#utilityinfo)
- **DELAY, ROUTE, EXPORT and SAVE OUTPUT** pause a run with a continue or cancel prompt, tidy long
  links, and save pictures, numbered files and animated GIFs. [UTILITY/IO](NODES.md#utilityio)

## Growing inputs

ARRAY, AKASHIC, FLATTEN, GRAPH, ROUTE, STACK and STRINGER add a new input each time the last one
is connected. Connected inputs are numbered, `0_IMAGE`, `1_IMAGE` and so on, and the node reads
them in that order.

## Vector widgets

VEC2, VEC3 and VEC4 inputs draw one field per component.

| Gesture | Result |
|---|---|
| Click a field | Type a value. Arithmetic such as `512*2` or `(1+2)/3` is worked out. |
| Drag across a field | Step the value up or down. |
| Shift-click the label | Reset to the default. |
| Click the label of a colour field | Invert the colour. |
| Click the swatch of a colour field | Open the colour picker. |

## Reading and saving files

QUEUE and QUEUE TOO read from ComfyUI's `input`, `output` and `temp` folders; EXPORT and SAVE
OUTPUT write into `output` or `temp`, or a folder below `output` typed as a relative path such as
`renders/shot1`.

To read or write another folder, name it in `ComfyUI/user/jovimetrix/config.json`:

```json
{
    "allow_read": ["D:/footage"],
    "allow_write": ["D:/deliveries"]
}
```

| Key | Default | What it does |
|---|---|---|
| `allow_read` | `[]` | Extra folders QUEUE and QUEUE TOO may read. |
| `allow_write` | `[]` | Extra folders EXPORT and SAVE OUTPUT may write into. |
| `gifski` | `""` | Full path of the gifski program, for EXPORT's `gifski` format. |
| `delay_min` | `5` | DELAY shows its prompt only for pauses longer than this, in seconds. |
| `delay_max` | `10000000` | Longest pause DELAY allows, in seconds. |

The file is read again whenever it changes. The variables `JOV_GIFSKI`, `JOV_DELAY_MIN` and
`JOV_DELAY_MAX` override the matching keys.

| Problem | Fix |
|---|---|
| `refusing to read` | Move the files into ComfyUI's `input` folder, or add their folder to `allow_read`. |
| `refusing to write into` | Clear the path to use `output`, type a relative path, or add the folder to `allow_write`. |
| `does not download web addresses` | Put the picture in ComfyUI's `input` folder, for example by dragging it from the browser onto a Load Image node, and list its file name. |
| `gifski is not set up` | Install gifski and put its full path in the `gifski` key. |
