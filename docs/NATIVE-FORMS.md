# Native forms (`forms.inc`)

GEM layer step 6 ([design](GEM-LAYER-DESIGN.md)): dialogs made of objects,
the counterpart of GEM's `objc_draw`, `objc_change`, `form_center`,
`form_dial` and `form_do`. Forms run in the app (bank 0) with the shared
graphics core; the AES image has no room left for them. While a form is open
it reads the keyboard and the 1351 pointer itself, like an AES alert, so the
menu bar stays inactive, as under GEM's `form_do`. Any graphical app can
include `src/native/forms.inc` (prefix `fo_`) after `graphics-core.inc`,
`text-core.inc` and `input/pointer.inc`. The AES is not required.

Before `fo_open`, the app binds the graphics core to its surface and stores
the surface's handle in `fo_surface`.

## Form record

A form is a header followed by its objects, in the app's memory:

| Byte | Header |
|---|---|
| 0, 1 | Cell x, y of the form box; x = `$ff` centres it: x = (40−w)/2, y = (25−h)/2 but at least 1 (y is then ignored) |
| 2, 3 | Width and height in cells, frame included (at most 38 × 23) |
| 4 | Object count, 1..32 |

Each object is 8 bytes; positions are cells relative to the form box:

| Byte | Object |
|---|---|
| 0 | Type: 1 text, 2 button, 3 checkbox, 4 radio button, 5 field |
| 1 | Flags: bit 0 default, bit 1 exit, bit 2 cancel (Esc), bits 4–7 radio group |
| 2 | State: bit 0 selected (checked), bit 1 disabled |
| 3, 4 | x, y |
| 5 | Width in cells (fields: the visible width) |
| 6, 7 | Text address (zero-terminated ASCII); a field's 8-byte `N_FEDIT` record |

A button is two rows high and `width` cells wide; its label is centred. A
checkbox or radio button is one row: a box or circle glyph, a space, then the
label. A field is one row of `width` cells, drawn from the record's 40-column
viewport, with its caret shown when it has focus. Its record and buffer
follow the [`N_FEDIT` rules](NATIVE-FIELDS.md): they must lie in the app's
own `$6000` allocation.

## Calls

| Call | Contract |
|---|---|
| `fo_open` | A/X = form. Centres it if asked, saves the cells under it in an owned heap allocation, initializes every field record (`N_FEDIT` key 0: caret at the end), draws it. Focus starts on the first focusable object. |
| `fo_do` | Runs the dialog until an exit: A = the exit object's index. |
| `fo_close` | Restores the saved cells exactly and frees the allocation. |
| `fo_redraw` | X = object: draws it again after the app changed its state or text. |

All return carry set with a native error code on a heap, graphics or `N_FEDIT` failure.
The form's state bytes are live: the app reads checks, radio choices and
field records after `fo_do`, and before or after `fo_close`.

## Input

| Input | Action |
|---|---|
| Tab, cursor down | Focus the next enabled button, checkbox, radio or field (wrapping) |
| Cursor up | Focus the previous one |
| Space | Toggle a checkbox; select a radio button (its group's others clear); press a button |
| Return | Press the focused button, else the default button |
| Esc | Press the cancel button, if there is one |
| Other keys on a field | Edited by `N_FEDIT`: printable keys, Left/Right, Home, Del, Ctrl-U |
| Click | Focus the object and act as Space (on a field: focus only) |

Pressing a button with the exit flag returns its index. A button without it
only takes focus. Disabled objects are drawn in grey, and never take focus
or act.

Forms draw only the VIC surface; they report no dirty rows for a VDC mirror.
Fields show no `<`/`>` edge marks; the view scrolls to keep the caret visible.

## Verification

GEMDESK's Show Info and Preferences dialogs are the tests
(`tests/ci_native_gemdesk.py`). Every state is compared as a complete surface
with `tests/native_forms_scene.py`. The cases cover:
- the initial focus on a field and on a checkbox;
- Ctrl-U and typing into a field, and Return taking the default button;
- Esc taking the cancel button, with exact restoration;
- Tab skipping text objects, cursor up, and a click on a button;
- Space toggling a checkbox;
- a click selecting a radio button and clearing its group;
- a disabled, checked checkbox.

Not yet covered by tests: a field narrower than its text (view scrolling),
focus wrapping, and a disabled button. Nothing has run in VICE or on hardware.
