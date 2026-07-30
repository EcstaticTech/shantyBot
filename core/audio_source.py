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
    
    # Local workspace check
    local_ffmpeg = Path("./ffmpeg.exe").resolve()
    if local_ffmpeg.exists():
        return str(local_ffmpeg)

    return "ffmpeg"

class MixedAudioSource(disnake.AudioSource):
    """FFmpeg amix audio source for real-time layering of tavern ambience over music tracks."""
    def __init__(self, main_track_path: str, ambient_path: str, ambient_volume: float = 0.3):
        self.main_path = str(Path(main_track_path).resolve())
        self.ambient_path = str(Path(ambient_path).resolve())
        self.process: subprocess.Popen | None = None

        filter_str = f"[1:a]volume={ambient_volume},aloop=loop=-1:size=2e+09[amb];[0:a][amb]amix=inputs=2:duration=first:dropout_transition=2[out]"
        
        ffmpeg_bin = _get_ffmpeg_executable()
        cmd = [
            ffmpeg_bin,
            "-re",
            "-i", self.main_path,
            "-i", self.ambient_path,
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
                stderr=subprocess.DEVNULL,
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
                return b""
            return ret
        except Exception as e:
            logger.error(f"Error reading PCM frame from FFmpeg process: {e}")
            return b""

    def cleanup(self):
        """Ensures child FFmpeg processes are cleanly terminated to prevent orphan handles on Windows."""
        if self.process:
            try:
                if self.process.stderr:
                    try:
                        self.process.stderr.flush()
                    except Exception:
                        pass
                self.process.kill()
                self.process.wait(timeout=1)
            except Exception as e:
                logger.warning(f"Error terminating FFmpeg subprocess: {e}")
            finally:
                self.process = None
