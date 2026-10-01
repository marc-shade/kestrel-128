.include "../../src/native/api.inc"
* = $6000
.include "../../src/native/graphics/graphics-core.inc"
.include "../../src/native/graphics/text-core.inc"
.cerror * > $6c00, "graphics test allocation exceeded"
