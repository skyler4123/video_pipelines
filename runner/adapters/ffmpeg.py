from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..errors import AdapterError
from .base import AdapterResult, BaseAdapter, Job

MEDIA_EXTENSIONS = {
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".wav",
    ".mp3",
    ".flac",
}


class FFmpegAdapter(BaseAdapter):
    name = "ffmpeg"

    def run(self, job: Job) -> AdapterResult:
        if job.action != "qc":
            raise AdapterError(
                f"ffmpeg action {job.action!r} is not implemented yet; "
                "only 'qc' is supported in this scaffold"
            )
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return AdapterResult(
                status="skipped",
                warnings=["ffprobe is not installed; QC was skipped"],
                extra={"skipped_reason": "ffprobe not found"},
            )

        existing_inputs = [path for path in job.input_paths if path.exists()]
        if not existing_inputs:
            return AdapterResult(
                status="failed",
                errors=[
                    "QC inputs do not exist: "
                    + ", ".join(str(path) for path in job.input_paths)
                ],
            )

        files = self._collect_files(job.input_paths)
        if not files:
            return AdapterResult(
                status="skipped",
                warnings=["QC found no media files in the previous stage output"],
                extra={"skipped_reason": "no media files"},
            )

        expected = job.qc or {}
        checks: list[dict[str, Any]] = []
        mismatches: list[str] = []
        probing_errors: list[str] = []

        for path in files:
            try:
                probe = self._probe(ffprobe, path)
            except AdapterError as exc:
                probing_errors.append(str(exc))
                continue
            info = self._extract(probe)
            file_mismatches = self._compare(path, info, expected)
            checks.append({"file": str(path), "info": info, "mismatches": file_mismatches})
            mismatches.extend(file_mismatches)

        errors = probing_errors + mismatches
        status = "failed" if errors else "succeeded"
        return AdapterResult(
            status=status,
            errors=errors,
            extra={"qc": {"checks": checks, "expected": expected}},
        )

    def _collect_files(self, paths: list[Path]) -> list[Path]:
        files: list[Path] = []
        for path in paths:
            if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
                files.append(path)
            elif path.is_dir():
                files.extend(
                    child
                    for child in sorted(path.iterdir())
                    if child.is_file() and child.suffix.lower() in MEDIA_EXTENSIONS
                )
        seen: set[Path] = set()
        unique: list[Path] = []
        for path in files:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                unique.append(path)
        return unique

    def _probe(self, ffprobe: str, path: Path) -> dict[str, Any]:
        command = [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, timeout=60, check=False
            )
        except OSError as exc:
            raise AdapterError(f"could not run ffprobe: {exc}") from exc
        except subprocess.TimeoutExpired as exc:
            raise AdapterError(f"ffprobe timed out for {path}") from exc
        if result.returncode != 0:
            raise AdapterError(
                f"ffprobe failed for {path}: {result.stderr.strip()[:1000]}"
            )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"ffprobe returned invalid JSON for {path}") from exc

    def _extract(self, probe: dict[str, Any]) -> dict[str, Any]:
        streams = probe.get("streams") or []
        video = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            None,
        )
        audio = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            None,
        )
        info: dict[str, Any] = {
            "has_video": video is not None,
            "has_audio": audio is not None,
        }
        if video:
            info["width"] = self._int(video.get("width"))
            info["height"] = self._int(video.get("height"))
            info["fps"] = self._fps(
                video.get("avg_frame_rate") or video.get("r_frame_rate")
            )
            info["frames"] = self._int(video.get("nb_frames"))
            info["codec"] = video.get("codec_name")
        if audio:
            info["audio_codec"] = audio.get("codec_name")
        fmt = probe.get("format") or {}
        info["duration"] = self._float(fmt.get("duration"))
        info["format"] = fmt.get("format_name")
        return info

    def _compare(
        self, path: Path, info: dict[str, Any], expected: dict[str, Any]
    ) -> list[str]:
        mismatches: list[str] = []
        for key in ("width", "height", "frames"):
            if expected.get(key) is None:
                continue
            actual = info.get(key)
            if actual != expected[key]:
                mismatches.append(
                    f"{path.name}: {key} is {actual}, expected {expected[key]}"
                )
        if expected.get("fps") is not None:
            actual = info.get("fps")
            if actual is None or abs(float(actual) - float(expected["fps"])) > 0.01:
                mismatches.append(
                    f"{path.name}: fps is {actual}, expected {expected['fps']}"
                )
        if expected.get("duration") is not None:
            actual = info.get("duration")
            if actual is None or abs(float(actual) - float(expected["duration"])) > 0.2:
                mismatches.append(
                    f"{path.name}: duration is {actual}, expected {expected['duration']}"
                )
        return mismatches

    @staticmethod
    def _int(value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _float(value: Any) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _fps(cls, value: Any) -> float | None:
        if not value or not isinstance(value, str):
            return None
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            try:
                if float(denominator) == 0:
                    return None
                return float(numerator) / float(denominator)
            except ValueError:
                return None
        return cls._float(value)
