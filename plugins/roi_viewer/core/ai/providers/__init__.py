# --------------------------------------------------------------------------
# Production AI providers (E6b+). Each module must be cheap to import: no
# AI framework at module level - frameworks are imported inside probe() /
# infer() only, and only after the user switches AI on. Listed in
# core/ai/registry.KNOWN_PROVIDER_MODULES.
# --------------------------------------------------------------------------
