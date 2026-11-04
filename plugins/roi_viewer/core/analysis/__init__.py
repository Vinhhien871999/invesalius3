# --------------------------------------------------------------------------
# ROI quantitative analysis (post-segmentation layer): statistics of the
# current ROI, HU classes inside it, ROI comparison, a transient analysis
# session and a report data model. Pure numpy/scipy - no wx, no pubsub, no
# invesalius import - so every result is testable without the application.
#
# Analysis never changes a mask, the E2 preview, the E4/E5 actors, the AI
# candidate or the final surface; the only path from an analysis result
# to a Project mask is the explicit "convert class to ROI" button, which
# commits through core/native_mask.commit_preview_array_to_new_mask() like
# every other candidate.
# --------------------------------------------------------------------------
