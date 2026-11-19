<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/Amorano/Jovimetrix-examples/master/res/logo-jovimetrix.png">
  <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/Amorano/Jovimetrix-examples/master/res/logo-jovimetrix-light.png">
  <img alt="Jovimetrix: ComfyUI nodes for procedural masking, live composition and animation" src="https://raw.githubusercontent.com/Amorano/Jovimetrix-examples/master/res/logo-jovimetrix.png">
</picture>

<h3 align="center">
<a href="https://github.com/comfyanonymous/ComfyUI">ComfyUI</a> nodes for procedural masking, live composition and animation
</h3>

Jovimetrix was created by Alexander G. Morano (Joviex) and is maintained by Jordan Thompson
(WASasquatch).

**53 nodes.** Every node, input and output is listed in [NODES.md](NODES.md); what the pack does
is in [FEATURES.md](FEATURES.md).

## Install

Jovimetrix 3 needs ComfyUI 0.14.0 or newer, and nothing else: it runs on torch, numpy, Pillow
and scipy, which ComfyUI installs.

**ComfyUI Manager.** Search for `Jovimetrix (WAS Fork)` and install it. Its registry id is
`jovimetrix-was`, so `comfy node install jovimetrix-was` works too.

**By hand.** Clone the pack into `ComfyUI/custom_nodes`:

```
cd ComfyUI/custom_nodes
git clone https://github.com/WASasquatch/Jovimetrix.git
```

Remove Alexander's original `Jovimetrix` first if it is installed. Both register the same nodes,
so only one of them can load.

## What changed in 3

- The nodes are built on ComfyUI's current node API. `cozy_comfyui` is no longer installed: the
  code Jovimetrix used from it ships inside the pack.
- Nothing to install. 2.x needed OpenCV, blendmodes, daltonlens, numba, scikit-learn,
  scikit-image, matplotlib, loguru and requests; 3.1 needs none of them. Picture work runs in
  torch, in floating point rather than 8-bit steps.
- QUEUE reads, and EXPORT and SAVE OUTPUT write, only inside ComfyUI's own folders and the folders
  named in `ComfyUI/user/jovimetrix/config.json`. See [Configuration](#configuration).
- Node titles drop `(JOV)`; the pack's badge on each node names it.
- Every input and output has a tooltip, and every node a description.
- Nothing is downloaded. Like ComfyUI's Load Image, QUEUE reads pictures from ComfyUI's folders,
  and the frontend loads nothing from outside the pack.

## Opening a 2.x workflow

Every node id, input name and input order is unchanged, so a 2.x workflow opens with every node
and link in place. These are the differences it shows:

| Node | What changed |
|---|---|
| Every node | The title drops `(JOV)` unless it was renamed. |
| Every picture node | Works in floating point rather than 8-bit steps, so results can differ from 2.x by a level. ADJUST: SHARPEN and the SOBEL, SCHARR and LAPLACIAN edges magnify that difference, because 2.x's rounding was magnified too. |
| Every picture node | Picture and mask outputs are lists. A batch still passes on as one batch, but a list of pictures of different sizes now passes through as a list of batches, a new batch starting wherever the size changes, where 2.x stopped with "stack expects each tensor to be equal size". A mask or picture that arrives without a batch dimension is read as one picture; 2.x read it as one picture per row. |
| Every node with a vector input | Editing one node's vector no longer changes the same input on other nodes of that type, or the value new nodes start with. A vector input wired to a subgraph input can be edited on the subgraph node. |
| ADJUST: LEVELS | In MANUAL mode, MID 0.5 now leaves the picture unchanged and lower values brighten. 2.x darkened the picture at the defaults. |
| ADJUST: COLOR | LAB and LUV no longer darken the picture at zero. |
| ADJUST: PIXEL | QUANTIZE reduces colours per pixel, and may settle on slightly different colours than 2.x. PIXELATE at 0 no longer takes minutes. |
| VALUE, LERP, OP UNARY, OP BINARY | With nothing wired into `a` or `b`, all of `aa` and `bb` is used. 2.x replaced their X with 0. VALUE's INT is an integer. Changing `type` away from BOOLEAN or INT gives the fields their full range again. |
| ARRAY | A mask batch is read as one mask per frame; 2.x read the whole batch as one picture. |
| TEXT GEN | Colours draw as set; 2.x swapped red and blue. A font missing on this machine falls back to the default instead of failing. |
| COLOR BLIND | 2.x swapped red and blue before simulating, so results differ. A `value` input for severity is added at the end. |
| COLOR MATCH | REINHARD matches in true LAB; USER_MAP's colour table runs dark to light. |
| COLOR MEANS | The LUT covers the whole colour range and its preview shows every slice. The colours found can differ slightly from 2.x. |
| BLEND | HUE, SATURATION, COLOR and LUMINOSITY blend the right channels. ADDITIVE and GLOW do what they say; 2.x drew both as NORMAL. With no `fore`, the background shows instead of a solid matte. |
| BLEND, CONSTANT | A `mask` given with a picture that has its own alpha keeps the lower of the two. 2.x combined their bits, which broke soft masks into patterns. |
| CROP | XY mode reads `xy` as a share of the picture, as its range of 0 to 1 suggests. |
| FLATTEN | ASPECT_SHORT works. |
| TRANSFORM | POLAR leaves the outside of the disc black; 2.x left whatever was in memory. A size that rounds below one pixel gives one pixel instead of an error. |
| GRADIENT MAP | `reverse` works. |
| PIXEL MERGE | `invert` works. |
| PIXEL SWAP | Alpha swaps work, and CONSTANT channels take the matte as RGBA. |
| WAVE GEN | `invert` and PULSE work. Outputs are lists, so one time gives one plain number. |
| TICK | `ease` NONE means no easing; QUINTIC_IN_OUT no longer jumps at its midpoint. |
| ROUTE, DELAY, BATCH TO LIST | Outputs are lists, so values pass on exactly as they arrived. 2.x split pictures into a list core nodes could not read, and DELAY passed on only the first entry. |
| QUEUE, QUEUE TOO | Paths outside the readable folders are refused. `recurse` works, a folder lists its pictures, and pictures load without their levels stretched. A photo with EXIF rotation loads upright, as Load Image does. INDEX is the current entry counted from 1 with `hold` or `batch` on too; 2.x gave one less there. A web address is no longer downloaded: QUEUE passes it on as text and QUEUE TOO refuses it. Put the picture in ComfyUI's `input` folder, for example by dragging it from the browser onto a Load Image node, and list its file name. |
| EXPORT | `path` is empty by default, meaning ComfyUI's output folder. A path outside the writable folders is refused; clear it, or add the folder to `allow_write`. |
| SAVE OUTPUT | Adds a number instead of replacing a file of the same name, unless the new `overwrite` input is on. Saved PNGs carry the workflow in the form ComfyUI loads. |
| GRAPH | Drawn without matplotlib, so the chart looks a little different. |

### Nodes that moved in 2.0

The GLSL, streaming, Spout, MIDI, help and colourising nodes left Jovimetrix in 2.0. A workflow
from before 2.0 that uses them needs the package that holds them now:
[Jovi_GLSL](https://github.com/Amorano/Jovi_GLSL),
[Jovi_Capture](https://github.com/Amorano/Jovi_Capture),
[Jovi_Spout](https://github.com/Amorano/Jovi_Spout),
[Jovi_MIDI](https://github.com/Amorano/Jovi_MIDI),
[Jovi_Help](https://github.com/Amorano/Jovi_Help) and
[Jovi_Colorizer](https://github.com/Amorano/Jovi_Colorizer).

## Configuration

Settings live in `ComfyUI/user/jovimetrix/config.json`, which is optional and is read again
whenever it changes. [config.example.json](config.example.json) shows every key.

| Key | Default | What it does |
|---|---|---|
| `allow_read` | `[]` | Extra folders QUEUE and QUEUE TOO may read. |
| `allow_write` | `[]` | Extra folders EXPORT and SAVE OUTPUT may write into. |
| `gifski` | `""` | Full path of the gifski program, for EXPORT's `gifski` format. |
| `delay_min` | `5` | DELAY shows its prompt only for pauses longer than this, in seconds. |
| `delay_max` | `10000000` | Longest pause DELAY allows, in seconds. |

The variables `JOV_GIFSKI`, `JOV_DELAY_MIN` and `JOV_DELAY_MAX` override the matching keys.
`allow_network`, read by 3.0 and 3.1, is ignored: Jovimetrix downloads nothing. What the pack may
read and write is set out in [SECURITY.md](SECURITY.md).

## Third-party code

Jovimetrix includes the code it used from `cozy_comfyui` (MIT), ports of blendmodes (MIT) and
DaltonLens (MIT), OpenCV's colour map tables, and code concepts from several other packs;
[NOTICE](NOTICE) lists each with its licence.

## Contributing

Report a problem or suggest a change at <https://github.com/WASasquatch/Jovimetrix/issues>.

## In memory of Alexander G. Morano

Alexander G. Morano, known to the ComfyUI community as Joviex, created Jovimetrix, the
`cozy_comfyui` library it grew from, and the family of Jovi packs, and gave them all away freely.
Alexander has passed away. Jovimetrix carries on in his memory.

[Alexander's obituary](https://www.dignitymemorial.com/obituaries/richmond-va/alexander-morano-12537385)

## License

MIT. See [LICENSE](LICENSE).
