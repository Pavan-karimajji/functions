#ifndef ADAS_FUNCTIONS_INTERFACE_C_H_
#define ADAS_FUNCTIONS_INTERFACE_C_H_

#include <stddef.h>
#include <stdint.h>

#if defined(_WIN32)
  #if defined(FUNCTIONS_SIL_EXPORTS)
    #define FN_API __declspec(dllexport)
  #else
    #define FN_API __declspec(dllimport)
  #endif
#else
  #define FN_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

/* Require-port buffer: one serialized input message + host-supplied metadata. */
typedef struct {
  const uint8_t* data;
  size_t len;
  double ageS;
  int valid;   /* 0/1 */
} FnReqBuf;

/* Provide-port buffer: caller-owned output storage (cap bytes); we fill up to len. */
typedef struct {
  uint8_t* data;
  size_t cap;
  size_t len;
  int updated;   /* 0/1 */
} FnProBuf;

/* Monotonic version, bumped whenever fnExec's signature/buffer semantics change (§5.8 item 2). */
FN_API int fnApiVersion(void);

/* configPath: path to a YAML file shaped like config/default.yaml. Returns NULL on error. */
FN_API void* fnInit(const char* configPath);

/* One cycle. objects/egoDyn: serialized GenObjectList/VehDyn (NULL if not received this tick).
   hypReaction/compState: caller-allocated output buffers (NULL if that output isn't wanted).
   Returns 1 on success, 0 on failure (e.g. null handle, output buffer too small). */
FN_API int fnExec(void* handle, double dtS,
                     const FnReqBuf* objects,
                     const FnReqBuf* egoDyn,
                     FnProBuf* hypReaction,
                     FnProBuf* compState);

FN_API void fnShutdown(void* handle);

#ifdef __cplusplus
}
#endif

#endif  /* ADAS_FUNCTIONS_INTERFACE_C_H_ */
