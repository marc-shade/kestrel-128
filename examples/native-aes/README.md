# Persistent AES example

`build.py OUTPUT` assembles `AESDEMO.PRG` (a native app) and `AESVC.PRG`
(the persistent bank-1 AES component, sealed for `$9000`). Put both files in
the same IEC disk or Ultimate folder and launch `AESDEMO`.

The first launch loads `AESVC.PRG`; Esc leaves it resident and a later launch
attaches to it with its attach counter intact. U unloads it. See
[NATIVE-AES](../../docs/NATIVE-AES.md) and `tests/ci_native_aes.py`.
