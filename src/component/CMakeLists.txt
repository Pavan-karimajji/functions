# df_common: framework + shared algo. Always built regardless of ENABLED_FUNCTIONS.
add_subdirectory(common)

# Per-function static libs, gated by ENABLED_FUNCTIONS (plan.md item 2 compile-time
# selection). Hand-maintained per-function block, not codegen/X-macros — not worth
# the machinery at ~7 functions (plan.md §5.7 Step 2 rationale). Add a new block here
# per .claude/workflows/add_function.md step 2 when a new function's skeleton lands.
if("aeb" IN_LIST ENABLED_FUNCTIONS)
    add_subdirectory(aeb)
    target_compile_definitions(fn_aeb PUBLIC ADAS_FN_AEB_ENABLED)
endif()
