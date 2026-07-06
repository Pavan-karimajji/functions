# C-API DLL Delivery Pattern (decided 2026-07-05, plan.md §5.6)

The primary SIL artifact of `modules/functions` is `functions_sil` — a **host-agnostic shared library** built from `src/platform/sil/`. Every simulator/middleware (CarMaker, CARLA, ROS2) is a thin binding on this one DLL. Never put algorithm code in a binding.

## The API (`src/platform/sil/functions_interface_c.h`)

```c
typedef struct { const uint8_t* data; size_t len; double ageS; int valid; } FnReqBuf;
typedef struct { uint8_t* data; size_t cap; size_t len; int updated; } FnProBuf;

int   fnApiVersion(void);               /* bump on any signature/semantics change */
void* fnInit(const char* configPath);   /* NULL on error */
int   fnExec(void* handle, double dtS,
              const FnReqBuf* objects,  /* serialized GenObjectList */
              const FnReqBuf* egoDyn,   /* serialized VehDyn        */
              FnProBuf* hypReaction,    /* out: serialized AebHypReaction */
              FnProBuf* compState);     /* out: serialized CompState  */
void  fnShutdown(void* handle);
```

## Rules

1. **Serialized protobuf across the boundary, always** (repo core rule: "protobuf contracts across boundaries only"). One contract definition; Python bindings come free via ctypes + protobuf.
2. **Host owns time.** The DLL never reads a clock — `dtS` and per-port `ageS` come from the caller (only the host knows receive times / sim time).
3. **Composition root lives inside the DLL** (`functions_interface_c.cpp`), guarded per function: `#ifdef ADAS_FN_<NAME>_ENABLED`.
4. **No crashes across the boundary**: `fnInit` returns NULL on bad config; `fnExec` returns non-zero on malformed buffers.
5. **Adding a function's ports extends `fnExec`'s parameters** → bump `fnApiVersion()`; bindings check it at load.
6. The DLL links no simulator/middleware libraries (verify: `dumpbin /dependents` — BCT-05 in docs/functions_swr_tests.md).

## Precedent

acdc2's `acdc2_interface_c.cpp` (`SF_Acdc2RequiredData`/`ProvidedData` set/exec pattern) and gen1's `Fn_senExecFCT_SEN(reqPorts, proPorts, …)` — in the reference world, SIL is always "the algo as a bindable library", never a middleware node.
