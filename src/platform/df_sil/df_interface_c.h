#ifndef ADAS_DF_INTERFACE_C_H_
#define ADAS_DF_INTERFACE_C_H_

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
#if defined(DF_SIL_EXPORTS)
#define DF_API __declspec(dllexport)
#else
#define DF_API __declspec(dllimport)
#endif
#else
#define DF_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Require-port buffer: one serialized input message + host-supplied metadata. */
typedef struct {
  const uint8_t* data;
  size_t len;
  double ageS;
  int valid; /* 0/1 */
} DfReqBuf;

/* Provide-port buffer: caller-owned output storage (cap bytes); we fill up to len. */
typedef struct {
  uint8_t* data;
  size_t cap;
  size_t len;
  int updated; /* 0/1 */
} DfProBuf;

/* Monotonic version, bumped whenever dfExec's signature/buffer semantics change (§5.8 item 2). */
DF_API int dfApiVersion(void);

/* configPath: path to a YAML file shaped like projects/base/default.yaml (or any
   other project's default.yaml, e.g. projects/proj_alpha/default.yaml — same
   shape, different calibration numbers). Returns NULL on error. */
DF_API void* dfInit(const char* configPath);

/* One cycle. objects/egoDyn: serialized GenObjectList/VehDyn (NULL if not received this tick).
   aebOutputs/compState: caller-allocated output buffers (NULL if that output isn't wanted).
   Returns 1 on success, 0 on failure (e.g. null handle, output buffer too small). */
DF_API int dfExec(void* handle, double dtS, const DfReqBuf* objects, const DfReqBuf* egoDyn,
                  DfProBuf* aebOutputs, DfProBuf* compState);

DF_API void dfShutdown(void* handle);

#ifdef __cplusplus
}
#endif

#endif /* ADAS_DF_INTERFACE_C_H_ */
