import os
import sys
import traceback

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _windows_tweaks():
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        ctypes.windll.winmm.timeBeginPeriod(1)
    except Exception:
        pass


def main():
    _windows_tweaks()
    from cybercup.game import Game
    Game().main_loop()


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        try:
            from cybercup import save_system
            os.makedirs(save_system.save_dir(), exist_ok=True)
            with open(os.path.join(save_system.save_dir(), "crash.log"), "w") as f:
                f.write(traceback.format_exc())
        except Exception:
            pass
        raise
