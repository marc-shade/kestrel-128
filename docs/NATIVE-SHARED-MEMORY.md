# Shared REU document memory

Editor uses one REU arena for documents and VDC screen backups inside
`VDSVC.PRG`. A memory lease keeps the provider and arena alive after graphics
closes; the display owns its snapshot independently. The memory service also
works when the VDC is unavailable. A clean REU or component refusal selects
the existing main-RAM document path. A failed probe restoration retains the
provider and blocks edits and exit until Escape can restore the saved bytes.

The suite's graphical Editor selects its backing store at the first input
loop, before it can open a document stream. Loading the optional component
there cannot replace an active document's file arguments. The choice remains
fixed for the app lifetime. This does not detect or recover from live changes
to the Ultimate REU size; changing that hardware configuration with live
allocations remains unsupported.

## Ownership and lifetime

The [foreground REU arena](NATIVE-REU.md) has one descriptor table, capacity
probe and app-generation cookie. Display snapshots use owner 32. Document
extents and undo records use owner 33, still tied to the foreground native app's generation.
The memory API cannot free a display token. Memory close refuses live
documents or history records. Display close frees its snapshot but leaves an active memory
lease intact. The provider can be unloaded only after both lifetimes end and
any probe or temporary-allocation recovery succeeds.

Each document has one resizable extent and an eight-byte token. Context byte
15 is an explicit backing tag: 0 for the existing RAM chunks, 1 for a shared
REU extent. The REU context has one handle at bytes 16–23; its capacity is the
extent's page count times 4096. Length, gap and positions remain 24-bit. RAM
contexts retain their 24-chunk limit; REU contexts can grow beyond 96 KiB,
up to available contiguous storage and the 24-bit capacity limit of 4095
pages. Allocated capacity is never treated as logical document data.

Growth first tries extending the current extent. If another allocation
blocks it, the service allocates a replacement, copies the old capacity in
512-byte transfers, and releases the old extent only after the copy completes.
The returned token changes only on successful relocation. A failed copy
preserves the original allocation and frees the temporary one; an uncertain
temporary free retains its token and is retried before the next operation.
Relocation needs enough free space for both allocations during the copy.

The document engine reserves storage before an insertion or replacement
changes logical data. Suite Editor replacements can remove a validated 24-bit
span while inserting at most 512 bytes. Removing a large selection reuses its
existing document extent; [undo history](NATIVE-HISTORY.md) can allocate a
separate record for the removed bytes, and zero-byte removal permits insertion at any valid position.
Failed transfers poison that document so Save As
cannot report success from uncertain bytes. New and controlled exit release
the owned extent explicitly. An uncertain file CLOSE follows the native
owner-quarantine path while retaining document and provider memory.

## Component interface

This is version 1 of the suite's internal memory protocol under native ABI
1.12. Call through `bk_call` directly; the display wrapper's automatic status
read would overwrite payload bytes. All calls return native A/carry results.
The executor retains its existing foreground, owner, generation, MMU and
interrupt checks.

Arguments use the transient heap mailbox, as defined in
[`shared-memory-api.inc`](../src/native/shared-memory-api.inc). Reload ordinary
heap arguments before calling a native heap entry afterward. File arguments
are separate. Offsets and multibyte values are little endian.

| Field | Address | Bytes | Meaning |
|---|---|---:|---|
| `SM_TOKEN` | `$3d00` | 8 | Opaque token; operation-specific status for Info/Stats |
| `SM_OFFSET` | `$3d08` | 3 | Byte offset within an extent |
| `SM_COUNT` | `$3d0b` | 2 | Requested transfer length; completed prefix on return |
| `SM_PAGES` | `$3d0d` | 2 | Requested total 4 KiB pages / total arena pages |
| `SM_PAGE` | `$3d0f` | 2 | First page / available pages |

| Operation | Name | Contract |
|---|---|---|
| 6 | Info | Token bytes: version, memory lease, arena active, probe recovery, temporary recovery, then three zeros |
| 7 | Open | Acquire the idempotent memory lease; retry probe restoration if needed |
| 8 | Allocate | Pages in; token and first page out on success |
| 9 | Read | Token/offset/count in; fetch 1–512 bytes into `N_BUFFER` |
| 10 | Write | Token/offset/count in; stash 1–512 bytes from `N_BUFFER` |
| 11 | Free | Release the matching document token |
| 12 | Resize | Token and requested total pages in; token and first page out on success |
| 13 | Close | Refuse live documents; release the memory lease after recovery |
| 14 | Stats | Total pages in Pages, available pages in Page, reusable slots in Token byte 0 |

Metadata never occupies `N_BUFFER`, so all 512 payload bytes survive range
selection and write dispatch. Resize may use that buffer for its internal
copy; Editor keeps insertion and file-verify input in its owned workspace.
Read/write report only completed DMA chunks. A failure in the checked call
gate precedes the provider and must be handled before reading its outputs.

## Software checks

`ci_native_reu_resize.py` checks growth against an independent interval model
at every supported REU size. `ci_native_shared_memory.py` executes the checked
bank-1 service, both display/memory acquisition orders, interrupted relocation
and full-byte integrity. `ci_native_document_reu.py` executes the shipped
Editor core and search module against independent byte arrays beyond 1 MiB,
including two contexts, random replacements, IRQs and metadata refusals.
`ci_native_editor_reu_documents.py` exercises the actual graphical app's large
files, capacity rollback, poisoned-document refusal and memory-only recovery.
These use software models and private images; physical qualification remains
pending. The [validation record](validation/2026-09-14-native-editor-reu-documents/README.md)
archives the exact executable inputs, test variants, emulator evidence and
independent rebuild.
