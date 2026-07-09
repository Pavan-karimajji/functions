# C-API DLL Delivery Pattern (decided 2026-07-05, plan.md §5.6)

The primary SIL artifact of `modules/df` is `df_sil` — a **host-agnostic shared library** built from `src/platform/df_sil/`. Every simulator/middleware (CarMaker, CARLA, ROS2) is a thin binding on this one DLL. Never put algorithm code in a binding.

## The API (`src/platform/df_sil/df_interface_c.h`)

```c
typedef struct { const uint8_t* data; size_t len; double ageS; int valid; } DfReqBuf;
typedef struct { uint8_t* data; size_t cap; size_t len; int updated; } DfProBuf;

int   dfApiVersion(void);               /* bump on any signature/semantics change */
void* dfInit(const char* configPath);   /* NULL on error */
int   dfExec(void* handle, double dtS,
              const DfReqBuf* objects,  /* serialized GenObjectList */
              const DfReqBuf* egoDyn,   /* serialized VehDyn        */
              DfProBuf* aebOutputs,     /* out: serialized AebOutputs */
              DfProBuf* compState);     /* out: serialized CompState  */
void  dfShutdown(void* handle);
```

## Rules

1. **Serialized protobuf across the boundary, always** (repo core rule: "protobuf contracts across boundaries only"). One contract definition; Python bindings come free via ctypes + protobuf.
2. **Host owns time.** The DLL never reads a clock — `dtS` and per-port `ageS` come from the caller (only the host knows receive times / sim time).
3. **Composition root lives inside the DLL** (`df_interface_c.cpp`), guarded per function: `#ifdef ADAS_FN_<NAME>_ENABLED`.
4. **No crashes across the boundary**: `dfInit` returns NULL on bad config; `dfExec` returns non-zero on malformed buffers.
5. **Adding a function's ports extends `dfExec`'s parameters** → bump `dfApiVersion()`; bindings check it at load.
6. The DLL links no simulator/middleware libraries (verify: `dumpbin /dependents` — BCT-05 in docs/df_swr_tests.md).

## Precedent

acdc2's `acdc2_interface_c.cpp` (`SF_Acdc2RequiredData`/`ProvidedData` set/exec pattern) and gen1's `Fct_senExecFCT_SEN(reqPorts, proPorts, …)` — in the reference world, SIL is always "the algo as a bindable library", never a middleware node.
