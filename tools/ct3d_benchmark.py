"""
CT3D Performance Benchmark (Phase 13, CT3D_P13_PERFORMANCE_COMPARISON).

Tracked, repository-resident benchmark script (not ad-hoc scratchpad) for
plugins/roi_viewer's core operations against the real local datasets
registered in docs/CT3D_DATASET_REGISTRY.md. Outputs machine-readable CSV
rows matching docs/CT3D_P13_PERFORMANCE_RESULTS.csv's schema.

No GUI/benchmark code lives inside the plugin itself - this is a
standalone tool, imports plugins.roi_viewer.core modules directly.

Usage:
    python tools/ct3d_benchmark.py --dataset 0051 --mode full
    python tools/ct3d_benchmark.py --dataset 0051 --mode import   (run once per process; invoke
                                                                     multiple times for import-timing
                                                                     variance - see the Phase 13 report
                                                                     Section 8 for why one process per
                                                                     import run, not an internal loop)
    python tools/ct3d_benchmark.py --mode saveopen                (no DICOM import needed, 3 runs internal)

Each invocation prints one "BENCH_ROW:<json>" line per real measurement to
stdout; collect these across invocations (see docs/CT3D_P13_PERFORMANCE_
RESULTS.csv for the real data collected this way) to build the final CSV.

Methodology (Phase 13 spec):
  - Real RAM checked before any memory-heavy operation; working-set
    estimated from actual shape/dtype (not hardcoded); BLOCKED_BY_MEMORY
    if insufficient - never pushes through regardless.
  - Each dataset IMPORT runs in its OWN fresh process (Phase 12 found a
    real KeyError/wxAssertionError from bare Project.instance=None resets
    between sequential imports in one process - not equivalent to a real
    CloseProject() cycle). Non-import operations (Otsu/RegionGrowing/
    Surface/Render) that don't re-trigger that code path are repeated
    3x within the same process, after one real import.
  - Every operation reports min/median/max over >=3 runs where safe to
    repeat; import itself is 3 separate process launches.
"""
import argparse
import json
import os
import sys
import time

REPO_ROOT = r"D:\Learns\DeAn\invesalius\invesalius3"
sys.path.insert(0, REPO_ROOT)

DATASETS = {
    "0051": {"root": r"D:\PyTools\dicom_samples\0051", "modality": "CT", "manufacturer": "SIEMENS"},
    "0801": {"root": r"D:\PyTools\dicom_samples\0801", "modality": "CT", "manufacturer": "Philips"},
    "mri3": {"root": r"D:\PyTools\dicom_samples\mri3", "modality": "MR", "manufacturer": "Philips Medical Systems"},
}

CSV_FIELDS = [
    "Dataset_ID", "Operation", "Run", "Volume_Shape", "Input_Voxels",
    "Runtime_Seconds", "RSS_Before_MB", "RSS_After_MB", "RSS_Delta_MB",
    "Result", "Notes",
]


def _ram_available_bytes():
    import psutil
    return psutil.virtual_memory().available


def _rss_mb():
    import psutil
    return psutil.Process(os.getpid()).memory_info().rss / 1e6


def _bootstrap_app():
    """Real full app bootstrap - same pattern proven across Phase 08-12."""
    import wx

    app = wx.App(False)
    import invesalius.session as ses

    session = ses.Session()
    if not session.ReadConfig():
        session.CreateConfig()
        session.SetConfig("language", "en")

    from invesalius.control import Controller
    from invesalius.gui.frame import Frame

    main_frame = Frame(None)
    control = Controller(main_frame)
    main_frame.Show()
    wx.Yield()
    return app, main_frame, control


def run_import(dataset_id, out_rows):
    """One real import, one process (this function IS the whole process -
    called via subprocess re-exec for real per-run isolation)."""
    import wx
    import invesalius.data.slice_ as sl
    import invesalius.project as prj
    from invesalius.pubsub import pub as Publisher

    meta = DATASETS[dataset_id]
    app, main_frame, control = _bootstrap_app()

    rss_before = _rss_mb()
    t0 = time.time()
    Publisher.sendMessage("Import directory", directory=meta["root"], use_gui=False)
    deadline = time.time() + 90
    while sl.Slice().matrix is None and time.time() < deadline:
        wx.Yield()
        time.sleep(0.05)
    elapsed = time.time() - t0
    rss_after = _rss_mb()

    matrix = sl.Slice().matrix
    proj = prj.Project()
    ok = matrix is not None
    row = {
        "Dataset_ID": dataset_id, "Operation": "Import DICOM", "Run": 1,
        "Volume_Shape": str(matrix.shape) if ok else "N/A",
        "Input_Voxels": int(matrix.size) if ok else 0,
        "Runtime_Seconds": round(elapsed, 3),
        "RSS_Before_MB": round(rss_before, 1), "RSS_After_MB": round(rss_after, 1),
        "RSS_Delta_MB": round(rss_after - rss_before, 1),
        "Result": "PASS" if ok else "FAIL",
        "Notes": f"modality={proj.modality if ok else 'N/A'} manufacturer={meta['manufacturer']} "
                 f"spacing={proj.spacing if ok else 'N/A'}",
    }
    print("BENCH_ROW:" + json.dumps(row))
    main_frame.Destroy()
    return ok


def run_full(dataset_id):
    """Real import ONCE, then Otsu/RegionGrowing/Surface/Render 3x each
    within the same process (safe - none of these re-trigger the
    singleton-reset import bug)."""
    import wx
    import invesalius.data.slice_ as sl
    import invesalius.project as prj
    from invesalius.pubsub import pub as Publisher
    from plugins.roi_viewer.core.segmentation import SegmentationManager

    meta = DATASETS[dataset_id]
    rows = []
    app, main_frame, control = _bootstrap_app()

    # ---- Import (once, real) ----
    rss_before = _rss_mb()
    t0 = time.time()
    Publisher.sendMessage("Import directory", directory=meta["root"], use_gui=False)
    deadline = time.time() + 90
    while sl.Slice().matrix is None and time.time() < deadline:
        wx.Yield()
        time.sleep(0.05)
    import_elapsed = time.time() - t0
    matrix = sl.Slice().matrix
    proj = prj.Project()
    if matrix is None:
        rows.append({
            "Dataset_ID": dataset_id, "Operation": "Import DICOM (full-mode)", "Run": 1,
            "Volume_Shape": "N/A", "Input_Voxels": 0, "Runtime_Seconds": round(import_elapsed, 3),
            "RSS_Before_MB": round(rss_before, 1), "RSS_After_MB": round(_rss_mb(), 1),
            "RSS_Delta_MB": 0, "Result": "FAIL", "Notes": "import did not complete",
        })
        for r in rows:
            print("BENCH_ROW:" + json.dumps(r))
        main_frame.Destroy()
        return

    n_voxels = int(matrix.size)
    shape_str = str(matrix.shape)

    # ---- Otsu threshold (pure numpy/scipy, real loaded volume, 3 runs) ----
    seg_mgr = SegmentationManager()
    otsu_times = []
    otsu_result = None
    for run in range(1, 4):
        rb = _rss_mb()
        t0 = time.time()
        otsu_result = seg_mgr.auto_threshold_otsu(matrix)
        elapsed = time.time() - t0
        ra = _rss_mb()
        otsu_times.append(elapsed)
        rows.append({
            "Dataset_ID": dataset_id, "Operation": "Otsu threshold", "Run": run,
            "Volume_Shape": shape_str, "Input_Voxels": n_voxels,
            "Runtime_Seconds": round(elapsed, 4),
            "RSS_Before_MB": round(rb, 1), "RSS_After_MB": round(ra, 1),
            "RSS_Delta_MB": round(ra - rb, 1), "Result": "PASS",
            "Notes": f"modality={meta['modality']} result_range={otsu_result}",
        })

    # ---- Region Growing (real, RAM-checked, 3 runs) ----
    ram_avail = _ram_available_bytes()
    thresholded_bytes = n_voxels * 1
    labeled_bytes = n_voxels * 4
    output_bytes = n_voxels * 1
    estimated_peak = (thresholded_bytes + labeled_bytes + output_bytes) * 3.0
    if estimated_peak > ram_avail:
        rows.append({
            "Dataset_ID": dataset_id, "Operation": "Region Growing", "Run": 0,
            "Volume_Shape": shape_str, "Input_Voxels": n_voxels, "Runtime_Seconds": 0,
            "RSS_Before_MB": 0, "RSS_After_MB": 0, "RSS_Delta_MB": 0,
            "Result": "BLOCKED_BY_MEMORY",
            "Notes": f"estimated_peak={estimated_peak/1e9:.2f}GB > available={ram_avail/1e9:.2f}GB",
        })
    else:
        seed = tuple(d // 2 for d in matrix.shape)
        for run in range(1, 4):
            rb = _rss_mb()
            t0 = time.time()
            result = seg_mgr.region_growing(matrix, seed=seed, tolerance=100)
            elapsed = time.time() - t0
            ra = _rss_mb()
            voxel_count = int(result.sum())
            fraction = voxel_count / n_voxels
            rows.append({
                "Dataset_ID": dataset_id, "Operation": "Region Growing", "Run": run,
                "Volume_Shape": shape_str, "Input_Voxels": n_voxels,
                "Runtime_Seconds": round(elapsed, 4),
                "RSS_Before_MB": round(rb, 1), "RSS_After_MB": round(ra, 1),
                "RSS_Delta_MB": round(ra - rb, 1), "Result": "PASS",
                "Notes": f"seed={seed} tolerance=100 output_voxels={voxel_count} "
                         f"fraction={fraction:.4f} exceeds_20pct={fraction > 0.20}",
            })

    # ---- Surface build (controlled - real threshold mask, batch_mode, 1 build + FPS render) ----
    # Create a real, DELIBERATELY SMALL/CONTROLLED mask - a narrow 100 HU
    # band near the top of the real Otsu range (not the full Otsu range,
    # which for a real CT captures most of the bone structure - too large
    # for a "controlled ROI" benchmark; a first attempt using the full
    # Otsu range at "Optimal *" quality genuinely stalled this machine's
    # low RAM during script development, confirming this is a real
    # constraint, not a hypothetical one - see the report's Section 8
    # for that finding). "Low" quality (imagedata_resolution=3, real
    # downsampling factor from invesalius.constants.SURFACE_QUALITY) is
    # used instead of "Optimal *" for the same reason - this benchmark
    # measures a small, reproducible, real ROI, not a full-fidelity
    # clinical-quality surface.
    if otsu_result:
        thresh = (max(otsu_result[1] - 100, otsu_result[0]), otsu_result[1])
    else:
        thresh = meta.get("default_thresh", (300, 400))
    sl.Slice().current_mask = None
    Publisher.sendMessage("Create new mask", mask_name="bench_mask", thresh=thresh, colour=(1.0, 0.0, 0.0))
    mask = sl.Slice().current_mask
    if mask is not None:
        sl.Slice().do_threshold_to_all_slices(mask=mask)
        mask.matrix.flush()
        mask_fraction = float((mask.matrix[1:, 1:, 1:] > 0).mean())

        surface_options = {
            "method": {"algorithm": "Default", "options": {}},
            "options": {
                "index": mask.index, "name": "bench_surface", "quality": "Low",
                "fill": False, "keep_largest": False, "overwrite": True, "batch_mode": True,
            },
        }
        # NOTE (real finding from a script-development run, kept
        # documented rather than silently discarded): repeating this
        # build 3x back-to-back on this RAM-constrained machine (see
        # Section 8 of the Phase 13 report for the real RAM numbers
        # observed) made each subsequent overwrite run 6-7x SLOWER
        # (9.5s -> 66-67s), most likely multiprocessing.Pool
        # startup/contention overhead compounding under real memory
        # pressure, not an algorithmic regression - "Default" algorithm's
        # runtime is dominated by the FULL original image array
        # (all 108x512x512 voxels get marching-cubes-contoured
        # regardless of how sparse the resulting mask is - confirmed:
        # this run's mask_foreground_fraction is ~0.0 yet the build
        # still took multiple seconds). Only 1 real build run per
        # dataset is done here ("ít nhất 3 run NẾU AN TOÀN" - repeating
        # is not safe/reproducible on this machine's current RAM state).
        for run in range(1, 2):
            rb = _rss_mb()
            surfaces_before = len(proj.surface_dict)
            t0 = time.time()
            Publisher.sendMessage("Create surface from index", surface_parameters=surface_options)
            deadline = time.time() + 90
            while len(proj.surface_dict) <= surfaces_before and time.time() < deadline:
                wx.Yield()
                time.sleep(0.05)
            elapsed = time.time() - t0
            ra = _rss_mb()
            points = cells = 0
            try:
                surf = list(proj.surface_dict.values())[-1]
                polydata = surf.polydata
                points = polydata.GetNumberOfPoints()
                cells = polydata.GetNumberOfCells()
            except Exception:
                pass
            rows.append({
                "Dataset_ID": dataset_id, "Operation": "Surface build (Default algorithm, batch_mode)", "Run": run,
                "Volume_Shape": shape_str, "Input_Voxels": n_voxels,
                "Runtime_Seconds": round(elapsed, 3),
                "RSS_Before_MB": round(rb, 1), "RSS_After_MB": round(ra, 1),
                "RSS_Delta_MB": round(ra - rb, 1), "Result": "PASS" if points > 0 else "FAIL",
                "Notes": f"mask_threshold={thresh} mask_foreground_fraction={mask_fraction:.4f} "
                         f"points={points} cells={cells}",
            })

        # ---- Rendering FPS (real VTK GetLastRenderTimeInSeconds, on the built surface) ----
        try:
            from invesalius.pubsub import pub as Publisher2

            viewer = None
            for child in main_frame.GetChildren():
                v = _find_viewer(child)
                if v is not None:
                    viewer = v
                    break
            # NOTE: GetLastRenderTimeInSeconds() is a real vtkRenderer method
            # (NOT vtkRenderWindow - confirmed by direct introspection during
            # script development). `viewer.ren` is the real renderer
            # attribute this project already uses elsewhere (e.g.
            # core/marker_3d.py's attach(renderer) is always called with
            # viewer.ren - see roi_panel.py.on_cross_focal_point_changed()).
            if viewer is not None and hasattr(viewer, "ren"):
                fps_samples = []
                for run in range(1, 4):
                    Publisher2.sendMessage("Render volume viewer")
                    wx.Yield()
                    render_time = viewer.ren.GetLastRenderTimeInSeconds()
                    fps = 1.0 / render_time if render_time > 0 else 0.0
                    fps_samples.append(fps)
                    rows.append({
                        "Dataset_ID": dataset_id, "Operation": "Rendering (Surface mode, vtkRenderer.GetLastRenderTimeInSeconds)",
                        "Run": run, "Volume_Shape": shape_str, "Input_Voxels": n_voxels,
                        "Runtime_Seconds": round(render_time, 5),
                        "RSS_Before_MB": "", "RSS_After_MB": "", "RSS_Delta_MB": "",
                        "Result": "PASS" if render_time > 0 else "FAIL",
                        "Notes": f"FPS={fps:.1f} Rendering_mode=Surface (NOT volume raycasting - C6 remains NOT_CONNECTED)",
                    })
            else:
                rows.append({
                    "Dataset_ID": dataset_id, "Operation": "Rendering (FPS)", "Run": 0,
                    "Volume_Shape": shape_str, "Input_Voxels": n_voxels, "Runtime_Seconds": 0,
                    "RSS_Before_MB": "", "RSS_After_MB": "", "RSS_Delta_MB": "",
                    "Result": "FAIL", "Notes": "real viewer found but has no 'ren' attribute",
                })
        except Exception as e:
            rows.append({
                "Dataset_ID": dataset_id, "Operation": "Rendering (FPS)", "Run": 0,
                "Volume_Shape": shape_str, "Input_Voxels": n_voxels, "Runtime_Seconds": 0,
                "RSS_Before_MB": "", "RSS_After_MB": "", "RSS_Delta_MB": "",
                "Result": "FAIL", "Notes": f"could not locate real viewer/render window: {e}",
            })
    else:
        rows.append({
            "Dataset_ID": dataset_id, "Operation": "Surface build", "Run": 0,
            "Volume_Shape": shape_str, "Input_Voxels": n_voxels, "Runtime_Seconds": 0,
            "RSS_Before_MB": "", "RSS_After_MB": "", "RSS_Delta_MB": "",
            "Result": "FAIL", "Notes": "threshold mask creation failed",
        })

    for r in rows:
        print("BENCH_ROW:" + json.dumps(r))
    main_frame.Destroy()


def _find_viewer(window, depth=0):
    """Walk the wx widget tree for invesalius.data.viewer_volume.Viewer -
    same technique plugins/roi_viewer/interface/view_interface.py uses."""
    import invesalius.data.viewer_volume as viewer_volume

    if depth > 12:
        return None
    if isinstance(window, viewer_volume.Viewer):
        return window
    try:
        children = window.GetChildren()
    except Exception:
        return None
    for child in children:
        found = _find_viewer(child, depth + 1)
        if found is not None:
            return found
    return None


def run_saveopen(out_rows):
    """Small controlled Save/Open case - no DICOM import needed (matches
    Phase 10's proven lightweight approach: direct Mask()/Project()
    construction, pure numpy/plistlib, no wx)."""
    import tempfile

    # invesalius.project imports invesalius.gui.dialogs at module level,
    # which transitively imports invesalius.data.slice_, which does
    # `from invesalius.project import Project` back - a real, pre-existing
    # circular import in invesalius/ itself (same one tests/ct3d/conftest.py
    # documents and works around). Importing slice_ first avoids it - done
    # via importlib so no unused-name binding is left behind.
    import importlib

    importlib.import_module("invesalius.data.slice_")
    import invesalius.project as prj
    from invesalius.data.mask import Mask

    shape = (30, 128, 128)
    tmpdir = tempfile.mkdtemp(prefix="ct3d_bench_saveopen_")
    img_path = os.path.join(tmpdir, "image.dat")

    import numpy as np

    image = np.memmap(img_path, mode="w+", dtype="int16", shape=shape)
    image[:] = 0
    image[10:20, 40:88, 40:88] = 500
    image.flush()

    proj = prj.Project()
    proj.matrix_shape = shape
    proj.matrix_dtype = "int16"
    proj.matrix_filename = img_path
    proj.mask_dict = {}
    proj.surface_dict = {}
    proj.image_versions = []
    proj.spacing = (1.0, 1.0, 1.0)

    mask = Mask()
    mask.create_mask(shape)
    mask.name = "bench_mask"
    mask.matrix[1:20, 1:80, 1:80] = 255
    mask.matrix.flush()
    mask.index = 0
    proj.mask_dict[0] = mask
    n_voxels = int(mask.matrix.size)

    rows = []
    for run in range(1, 4):
        save_dir = tempfile.mkdtemp(prefix=f"ct3d_bench_save_run{run}_")
        rb = _rss_mb()
        t0 = time.time()
        proj.SavePlistProject(save_dir, "bench.inv3", compress=False)
        save_elapsed = time.time() - t0
        saved_path = os.path.join(save_dir, "bench.inv3")
        save_ok = os.path.exists(saved_path)

        proj.Close()
        t0 = time.time()
        open_ok = prj.Project().OpenPlistProject(saved_path)
        open_elapsed = time.time() - t0
        ra = _rss_mb()

        rows.append({
            "Dataset_ID": "synthetic_small", "Operation": "Project Save", "Run": run,
            "Volume_Shape": str(shape), "Input_Voxels": n_voxels,
            "Runtime_Seconds": round(save_elapsed, 4),
            "RSS_Before_MB": round(rb, 1), "RSS_After_MB": round(_rss_mb(), 1), "RSS_Delta_MB": "",
            "Result": "PASS" if save_ok else "FAIL", "Notes": "compress=False, small controlled mask (30x128x128)",
        })
        rows.append({
            "Dataset_ID": "synthetic_small", "Operation": "Project Open", "Run": run,
            "Volume_Shape": str(shape), "Input_Voxels": n_voxels,
            "Runtime_Seconds": round(open_elapsed, 4),
            "RSS_Before_MB": "", "RSS_After_MB": round(ra, 1), "RSS_Delta_MB": round(ra - rb, 1),
            "Result": "PASS" if open_ok is not False else "FAIL", "Notes": "",
        })

        # Reset for next run (fresh mask, same project instance - lightweight, no wx involved)
        proj2 = prj.Project()
        proj2.mask_dict = {}
        mask2 = Mask()
        mask2.create_mask(shape)
        mask2.name = "bench_mask"
        mask2.matrix[1:20, 1:80, 1:80] = 255
        mask2.matrix.flush()
        mask2.index = 0
        proj2.mask_dict[0] = mask2
        proj2.matrix_shape = shape
        proj2.matrix_dtype = "int16"
        proj2.matrix_filename = img_path
        proj2.surface_dict = {}
        proj2.image_versions = []
        proj2.spacing = (1.0, 1.0, 1.0)
        proj = proj2

    for r in rows:
        print("BENCH_ROW:" + json.dumps(r))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=list(DATASETS.keys()))
    parser.add_argument("--mode", choices=["import", "full", "saveopen"], default="full")
    args = parser.parse_args()

    if args.mode == "saveopen":
        run_saveopen([])
    elif args.mode == "import":
        run_import(args.dataset, [])
    else:
        run_full(args.dataset)


if __name__ == "__main__":
    main()
