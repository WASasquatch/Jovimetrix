# Security

A workflow is a document someone else may have written. These are the limits Jovimetrix holds
every workflow to, whoever wrote it.

## Files

| Action | Folders |
|---|---|
| Read (QUEUE, QUEUE TOO) | ComfyUI `input`, `output` and `temp`, the pack's own `res` folder, and every folder in `allow_read` |
| Write (EXPORT, SAVE OUTPUT) | ComfyUI `output` and `temp`, and every folder in `allow_write` |
| Write refused | Everything else, including ComfyUI `input` |

- A path is resolved, links included, before it is compared with these folders. A path outside
  them is refused with a message naming the path as typed and the folders by name only.
- Every file a QUEUE pattern or folder finds is checked again by its own resolved path.
- A file name typed into EXPORT or SAVE OUTPUT is one plain name: a separator, a drive, `..`, a
  trailing dot or a Windows device name such as `NUL` is refused.
- EXPORT and SAVE OUTPUT add a number to a new file rather than replace an existing one, unless
  `overwrite` is on.
- The only files Jovimetrix deletes are the PNG frames EXPORT writes into ComfyUI `temp` for
  gifski, by name, followed by their empty folder.

## Programs

- EXPORT runs one program, gifski, and only from the path in the `gifski` setting or the
  `JOV_GIFSKI` variable. It is started with an argument list, never through a shell, so nothing a
  workflow types becomes a command.

## Network

- The Python side opens no outgoing connection. No node downloads anything: a web address in a
  QUEUE list passes on as text, and QUEUE TOO refuses one. There is no setting that turns
  downloading on; `allow_network`, which 3.0 and 3.1 read, is ignored.
- The browser side loads only the pack's own files. It fetches nothing from any other host.

## Routes

| Route | Method | Takes | Limits |
|---|---|---|---|
| `/jovimetrix/message` | POST | `{"id", "cmd", "client_id"}` | Body up to 4096 bytes; id and command up to 64 characters; 256 node ids with 8 messages each, oldest dropped |

A node reads a message only when it was sent by the browser tab that queued the run, or from
any tab for a run queued without a client id, such as one sent straight to the API. The events a
node sends (DELAY's prompt, QUEUE's progress) go to the tab that queued the run alone.

## Sizes

- A canvas a node builds is limited to 16384 pixels a side and 268435456 pixels in all, checked
  before anything is allocated. A TEXT GEN letter batch, a COLOR MEANS swatch batch and a QUEUE
  TOO batch are also limited to 1073741824 pixels across all their frames.
- A QUEUE list holds at most 50000 entries, and a `.txt` or `.json` file it reads is at most 16 MB.
- FACTORIAL above 170 returns the largest number a float holds, and bit shifts stop at 1024 bits.

## Reporting a problem

Open an issue at <https://github.com/WASasquatch/Jovimetrix/issues>. For something that should
not be public, say so in the issue and ask for a private contact.
