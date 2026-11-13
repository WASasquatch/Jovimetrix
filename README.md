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

Jovimetrix 3 needs ComfyUI 0.14.0 or newer.

**ComfyUI Manager.** Search for Jovimetrix and install it.

**By hand.** Clone the pack into `ComfyUI/custom_nodes` and install its requirements with the
Python that runs ComfyUI:

```
cd ComfyUI/custom_nodes
git clone https://github.com/WASasquatch/Jovimetrix.git
```

```
python_embeded\python.exe -m pip install -r ComfyUI\custom_nodes\Jovimetrix\requirements.txt
```

On a portable Windows install, run the second command from the folder holding `python_embeded`.
Elsewhere, use `python -m pip install -r requirements.txt` with ComfyUI's environment active.

The requirements are `opencv-contrib-python`, `blendmodes` and `daltonlens`.

## What changed in 3.0

- The nodes are built on ComfyUI's current node API. `cozy_comfyui` is no longer installed: the
  code Jovimetrix used from it ships inside the pack.
- Fewer packages: `numba`, `scikit-learn`, `scikit-image`, `matplotlib`, `loguru` and `requests`
  are no longer needed.
- QUEUE reads, and EXPORT and SAVE OUTPUT write, only inside ComfyUI's own folders and the folders
  named in `ComfyUI/user/jovimetrix/config.json`. See [Configuration](#configuration).
- Node titles drop `(JOV)`; the pack's badge on each node names it.
- Every input and output has a tooltip, and every node a description.
- The frontend loads nothing from outside the pack.

## Opening a 2.x workflow

Every node id, input name and input order is unchanged, so a 2.x workflow opens with every node
and link in place. These are the differences it shows:

| Node | What changed |
|---|---|
| Every node | The title drops `(JOV)` unless it was renamed. |
| ADJUST: LEVELS | In MANUAL mode, MID 0.5 now leaves the picture unchanged and lower values brighten. 2.x darkened the picture at the defaults. |
| ADJUST: COLOR | LAB and LUV no longer darken the picture at zero. |
| ADJUST: PIXEL | QUANTIZE reduces colours per pixel; PIXELATE at 0 no longer takes minutes. |
| VALUE, LERP, OP UNARY, OP BINARY | With nothing wired into `a` or `b`, all of `aa` and `bb` is used. 2.x replaced their X with 0. VALUE's INT is an integer. |
| TEXT GEN | Colours draw as set; 2.x swapped red and blue. A font missing on this machine falls back to the default instead of failing. |
| COLOR BLIND | 2.x swapped red and blue before simulating, so results differ. A `value` input for severity is added at the end. |
| COLOR MATCH | REINHARD matches in true LAB; USER_MAP's colour table runs dark to light. |
| COLOR MEANS | The LUT covers the whole colour range and its preview shows every slice. |
| BLEND | HUE, SATURATION, COLOR and LUMINOSITY blend the right channels. With no `fore`, the background shows instead of a solid matte. |
| CROP | XY mode reads `xy` as a share of the picture, as its range of 0 to 1 suggests. |
| GRADIENT MAP | `reverse` works. |
| PIXEL MERGE | `invert` works. |
| PIXEL SWAP | Alpha swaps work, and CONSTANT channels take the matte as RGBA. |
| WAVE GEN | `invert` and PULSE work. Outputs are lists, so one time gives one plain number. |
| TICK | `ease` NONE means no easing; QUINTIC_IN_OUT no longer jumps at its midpoint. |
| ROUTE, DELAY, BATCH TO LIST | Outputs are lists, so values pass on exactly as they arrived. 2.x split pictures into a list core nodes could not read, and DELAY passed on only the first entry. |
| QUEUE, QUEUE TOO | Paths outside the readable folders are refused. `recurse` works, a folder lists its pictures, and pictures load without their levels stretched. |
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
| `allow_network` | `false` | Let QUEUE and QUEUE TOO load `http` and `https` addresses. |
| `gifski` | `""` | Full path of the gifski program, for EXPORT's `gifski` format. |
| `delay_min` | `5` | DELAY shows its prompt only for pauses longer than this, in seconds. |
| `delay_max` | `10000000` | Longest pause DELAY allows, in seconds. |

The variables `JOV_GIFSKI`, `JOV_DELAY_MIN` and `JOV_DELAY_MAX` override the matching keys. What
the pack may read, write and fetch is set out in [SECURITY.md](SECURITY.md).

## Third-party code

Jovimetrix includes the code it used from `cozy_comfyui` (MIT) and code concepts from several
other packs; [NOTICE](NOTICE) lists each with its licence. It depends on OpenCV (Apache 2.0),
blendmodes (MIT) and daltonlens (MIT).

## Contributing

Report a problem or suggest a change at <https://github.com/WASasquatch/Jovimetrix/issues>.

## In memory of Alexander G. Morano

Alexander G. Morano, known to the ComfyUI community as Joviex, created Jovimetrix, the
`cozy_comfyui` library it grew from, and the family of Jovi packs, and gave them all away freely.
Alexander has passed away. Jovimetrix carries on in his memory.

[Alexander's obituary](https://www.dignitymemorial.com/obituaries/richmond-va/alexander-morano-12537385)

## License

MIT. See [LICENSE](LICENSE).
