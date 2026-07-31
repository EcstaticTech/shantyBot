import subprocess
import logging
import shutil
import disnake
from pathlib import Path

logger = logging.getLogger("shantyBot")

def _get_ffmpeg_executable() -> str:
    """Resolves FFmpeg executable location in system PATH or local workspace fallback."""
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    
    local_ffmpeg = Path("./ffmpeg.exe").resolve()
    if local_ffmpeg.exists():
        return str(local_ffmpeg)

    return "ffmpeg"

class MixedAudioSource(disnake.AudioSource):
    """FFmpeg amix audio source for real-time layering of ambient soundscapes over music tracks."""
    def __init__(self, main_track_path: str, ambient_path: str, ambient_volume: float = 0.3, seek_seconds: float = 0.0):
        self.main_path = str(Path(main_track_path).resolve())
        self.ambient_path = str(Path(ambient_path).resolve())
        self.seek_seconds = max(0.0, float(seek_seconds))
        self.process: subprocess.Popen | None = None

        filter_str = f"[1:a]volume={ambient_volume}[amb];[0:a]volume=1.0[main];[main][amb]amix=inputs=2:duration=first:dropout_transition=2[out]"
        
        ffmpeg_bin = _get_ffmpeg_executable()

        main_input = ["-ss", f"{self.seek_seconds:.2f}", "-i", self.main_path] if self.seek_seconds > 0 else ["-i", self.main_path]
        ambient_input = ["-stream_loop", "-1", "-i", self.ambient_path]

        cmd = [
            ffmpeg_bin,
            "-re",
            *main_input,
            *ambient_input,
            "-filter_complex", filter_str,
            "-map", "[out]",
            "-f", "s16le",
            "-ar", "48000",
            "-ac", "2",
            "pipe:1"
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=3840
            )
        except Exception as e:
            logger.error(f"Failed to spawn FFmpeg amix subprocess using '{ffmpeg_bin}': {e}")
            raise e

    def read(self) -> bytes:
        """Reads 20ms PCM audio frame (3840 bytes). Returns b"" on EOF or read failure."""
        if not self.process or not self.process.stdout:
            return b""
        try:
            ret = self.process.stdout.read(3840)
            if len(ret) != 3840:
                if self.process and self.process.stderr:
                    try:
                        err_out = self.process.stderr.read()
                        if err_out:
                            logger.warning(f"FFmpeg process stderr: {err_out.decode('utf-8', errors='ignore')}")
                    except Exception:
                        pass
                return b""
            return ret
        except Exception as e:
            logger.error(f"Error reading PCM frame from FFmpeg process: {e}")
            return b""

    def cleanup(self):
        """Ensures child FFmpeg processes are cleanly terminated to prevent orphan handles and pipe deadlocks."""
        proc = getattr(self, "process", None) or getattr(self, "_process", None)
        if proc:
            try:
                if proc.stdout:
                    try:
                        proc.stdout.close()
                    except (BrokenPipeError, ProcessLookupError, OSError):
                        pass
                if proc.stderr:
                    try:
                        proc.stderr.close()
                    except (BrokenPipeError, ProcessLookupError, OSError):
                        pass
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=1)
                    except Exception:
                        proc.kill()
            except Exception as e:
                logger.warning(f"Error terminating FFmpeg subprocess: {e}")
            finally:
                self.process = None

class SoloAmbientAudioSource(disnake.AudioSource):
    """FFmpeg endless loop audio source for standalone ambient soundscapes when queue is empty."""
    def __init__(self, ambient_path: str, ambient_volume: float = 0.5):
        self.ambient_path = str(Path(ambient_path).resolve())
        self.process: subprocess.Popen | None = None

        ffmpeg_bin = _get_ffmpeg_executable()
        cmd = [
            ffmpeg_bin,
            "-re",
            "-stream_loop", "-1",
            "-i", self.ambient_path,
            "-filter:a", f"volume={ambient_volume}",
            "-f", "s16le",
            "-ar", "48000",
            "-ac", "2",
            "pipe:1"
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=3840
            )
        except Exception as e:
            logger.error(f"Failed to spawn FFmpeg solo ambient subprocess using '{ffmpeg_bin}': {e}")
            raise e

    def read(self) -> bytes:
        if not self.process or not self.process.stdout:
            return b""
        try:
            ret = self.process.stdout.read(3840)
            if len(ret) != 3840:
                if self.process and self.process.stderr:
                    try:
                        err_out = self.process.stderr.read()
                        if err_out:
                            logger.warning(f"FFmpeg solo ambient stderr: {err_out.decode('utf-8', errors='ignore')}")
                    except Exception:
                        pass
                return b""
            return ret
        except Exception as e:
            logger.error(f"Error reading PCM frame from FFmpeg solo ambient process: {e}")
            return b""

    def cleanup(self):
        """Ensures child FFmpeg processes are cleanly terminated to prevent orphan handles and pipe deadlocks."""
        proc = getattr(self, "process", None) or getattr(self, "_process", None)
        if proc:
            try:
                if proc.stdout:
                    try:
                        proc.stdout.close()
                    except (BrokenPipeError, ProcessLookupError, OSError):
                        pass
                if proc.stderr:
                    try:
                        proc.stderr.close()
                    except (BrokenPipeError, ProcessLookupError, OSError):
                        pass
                if proc.poll() is None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=1)
                    except Exception:
                        proc.kill()
            except Exception as e:
                logger.warning(f"Error terminating FFmpeg subprocess: {e}")
            finally:
                self.process = None
