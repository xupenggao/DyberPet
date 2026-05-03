"""CLI entry point for the loop animation tool."""

import argparse
import sys

from .video_io import extract_frames, get_video_info
from .pose_estimator import PoseEstimator, is_available as pose_available
from .loop_finder import find_best_loop, apply_crossfade
from .bg_remover import remove_green_screen_batch, auto_detect_green_range, remove_bg_ai
from .exporter import export_frame_sequence, generate_act_conf_file


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract seamless loop animation from animal video for DyberPet",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect best method
  python -m tools.loop_maker -i cat_walk.mp4 -o ./output -n walk

  # Image similarity only (no GPU needed)
  python -m tools.loop_maker -i cat.mp4 -o ./output -n dance --method image

  # With green screen removal
  python -m tools.loop_maker -i cat_green.mp4 -o ./output -n walk --remove-bg green

  # With AI background removal
  python -m tools.loop_maker -i cat.mp4 -o ./output -n run --remove-bg ai
        """,
    )
    parser.add_argument("--input", "-i", required=True, help="Input video file path")
    parser.add_argument(
        "--output-dir", "-o", required=True, help="Output directory"
    )
    parser.add_argument(
        "--name", "-n", default="animation", help="Animation name prefix (default: animation)"
    )
    parser.add_argument(
        "--fps", type=float, default=12, help="Target FPS for extraction (default: 12)"
    )
    parser.add_argument(
        "--method",
        choices=["auto", "pose", "image"],
        default="auto",
        help="Similarity method: auto, pose, or image (default: auto)",
    )
    parser.add_argument(
        "--min-gap",
        type=int,
        default=10,
        help="Minimum frames between loop points (default: 10)",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=60,
        help="Maximum loop length in frames (default: 60)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Minimum similarity threshold 0-1 (default: 0.85)",
    )
    parser.add_argument(
        "--crossfade",
        type=int,
        default=0,
        help="Number of frames to crossfade at loop boundary (default: 0)",
    )
    parser.add_argument(
        "--size",
        type=str,
        default=None,
        help="Resize output frames, e.g. '128x128' (default: original size)",
    )
    parser.add_argument(
        "--frame-refresh",
        type=float,
        default=0.08,
        help="frame_refresh value for act_conf.json in seconds (default: 0.08)",
    )
    parser.add_argument(
        "--generate-conf",
        action="store_true",
        help="Generate act_conf.json alongside frames",
    )
    parser.add_argument(
        "--crop",
        type=str,
        default=None,
        help="Crop region as 'x,y,w,h' (e.g. '100,50,400,300')",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n-pose.pt",
        help="YOLOv8 pose model file (default: yolov8n-pose.pt)",
    )
    parser.add_argument(
        "--remove-bg",
        choices=["green", "ai", "none"],
        default="none",
        help="Background removal: green (chroma key), ai (rembg), or none (default: none)",
    )
    parser.add_argument(
        "--green-hue",
        type=str,
        default=None,
        help="Green screen hue range as 'min,max' (0-180, default: auto-detect)",
    )
    parser.add_argument(
        "--green-feather",
        type=int,
        default=3,
        help="Edge feathering radius for green screen removal (default: 3)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # Parse size
    size = None
    if args.size:
        parts = args.size.split("x")
        if len(parts) != 2:
            print("Error: --size format should be WxH, e.g. 128x128")
            return 1
        size = (int(parts[0]), int(parts[1]))

    # Parse crop
    crop = None
    if args.crop:
        parts = [int(x) for x in args.crop.split(",")]
        if len(parts) != 4:
            print("Error: --crop format should be x,y,w,h")
            return 1
        crop = tuple(parts)

    # Step 1: Video info
    print(f"Reading video: {args.input}")
    info = get_video_info(args.input)
    print(
        f"  {info['width']}x{info['height']}, {info['fps']:.1f} fps, "
        f"{info['total_frames']} frames, {info['duration']:.1f}s"
    )

    # Step 2: Extract frames
    print(f"Extracting frames (target FPS: {args.fps})...")
    frames, original_fps = extract_frames(args.input, target_fps=args.fps, crop=crop)
    print(f"  Extracted {len(frames)} frames")

    if len(frames) < args.min_gap * 2:
        print(
            f"Error: Not enough frames ({len(frames)}). "
            f"Need at least {args.min_gap * 2}. Try lowering --fps or --min-gap."
        )
        return 1

    # Step 3: Pose estimation (if requested/available)
    poses = None
    use_pose = False
    if args.method in ("auto", "pose"):
        if pose_available():
            print(f"Running pose estimation (model: {args.model})...")
            try:
                estimator = PoseEstimator(model_name=args.model)
                poses = estimator.estimate_poses(frames)
                rate = estimator.detection_rate(poses)
                print(f"  Detection rate: {rate:.0%}")
                if rate < 0.5:
                    print("  Low detection rate, will use image similarity as fallback")
                    use_pose = False
                else:
                    use_pose = True
            except Exception as e:
                print(f"  Pose estimation failed: {e}")
                if args.method == "pose":
                    return 1
                print("  Falling back to image similarity...")
                use_pose = False
        else:
            if args.method == "pose":
                print("Error: ultralytics not installed. Install with: pip install ultralytics")
                return 1
            print("ultralytics not installed, using image similarity")

    # Step 4: Find best loop
    start, end, score = find_best_loop(
        frames,
        poses=poses,
        min_gap=args.min_gap,
        max_frames=args.max_frames,
        similarity_threshold=args.threshold,
        use_pose=use_pose,
    )

    if start is None:
        print(f"No suitable loop found (best score: {score:.3f})")
        return 1

    # Step 5: Extract loop segment
    segment = frames[start:end]

    # Apply crossfade if requested
    if args.crossfade > 0:
        print(f"Applying crossfade ({args.crossfade} frames)...")
        segment = apply_crossfade(frames, start, end, blend_frames=args.crossfade)

    # Step 6: Background removal
    if args.remove_bg == "green":
        print("Removing green screen background...")
        hue_range = None
        if args.green_hue:
            parts = [int(x) for x in args.green_hue.split(",")]
            if len(parts) != 2:
                print("Error: --green-hue format should be min,max, e.g. 35,85")
                return 1
            hue_range = tuple(parts)
        else:
            hue_range = auto_detect_green_range(segment)
        segment = remove_green_screen_batch(
            segment,
            hue_range=hue_range,
            feather=args.green_feather,
        )
        print(f"  Green screen removed from {len(segment)} frames")
    elif args.remove_bg == "ai":
        print("Removing background with AI (rembg)...")
        try:
            segment = remove_bg_ai(segment)
            print(f"  Background removed from {len(segment)} frames")
        except RuntimeError as e:
            print(f"Error: {e}")
            return 1

    # Step 7: Export
    print(f"Exporting {len(segment)} frames...")
    saved = export_frame_sequence(segment, args.output_dir, args.name, size=size)
    print(f"  Saved to: {saved[0]} ... {saved[-1]}")

    # Step 8: Generate config
    if args.generate_conf:
        conf_path = generate_act_conf_file(
            args.name, len(segment), args.output_dir, args.frame_refresh
        )
        print(f"  Config: {conf_path}")

    # Summary
    duration = len(segment) * args.frame_refresh
    print(f"\nDone! Loop: {len(segment)} frames, ~{duration:.2f}s per cycle, similarity={score:.3f}")
    print(f"Copy 'action/' folder and merge 'act_conf.json' into your DyberPet character directory.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
