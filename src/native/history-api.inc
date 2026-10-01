; Foreground VDSVC text-span history, version 1. No resident ABI entries.
; BEGIN consumes N_BUFFER[0..8]: position, removed length, inserted length,
; each unsigned LE24. APPEND streams removed bytes followed by inserted bytes.
; A record becomes visible only after SEAL. ABORT preserves published history.
; PREPARE returns the same header, reversing lengths for Undo. READ streams the
; replacement bytes. APPLIED advances history only after the document succeeds.
; CLEAR consumes N_BUFFER[0]=current dirty flag; SAVE marks the current state.
; INFO/APPLIED return N_BUFFER[0]=dirty, [1]=undo count, [2]=redo count, [3]=1.
; Transfers use H_COUNT=1..512. Tokens and offsets remain inside the provider.
H_INFO=15
H_BEGIN=16
H_APPEND=17
H_SEAL=18
H_ABORT=19
H_UNDO=20
H_REDO=21
H_READ=22
H_APPLIED=23
H_CLEAR=24
H_SAVE=25
H_CLOSE=26
H_COUNT=N_COUNT
H_STEPS=16
H_HEADER=9
