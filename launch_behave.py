from pathlib import Path
import subprocess
import sys
import time
import webbrowser


ROOT = Path(__file__).resolve().parent


def main() -> None:
    processes: list[subprocess.Popen] = []
    try:
        print("Starting local demo agent (Agent v1 & v2)...")
        processes.append(
            subprocess.Popen([sys.executable, str(ROOT / "demo_agent.py")], cwd=ROOT)
        )

        print("Starting Behave Dashboard...")
        processes.append(
            subprocess.Popen([sys.executable, str(ROOT / "app.py")], cwd=ROOT)
        )

        time.sleep(2)
        if any(process.poll() is not None for process in processes):
            raise RuntimeError("A Behave process failed to start; check the output above.")

        url = "http://127.0.0.1:5000"
        print(f"Opening {url}")
        webbrowser.open(url)
        print("Behave is running. Press Ctrl+C to stop.")
        processes[-1].wait()
    except KeyboardInterrupt:
        print("\nStopping Behave...")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            if process.poll() is None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()


if __name__ == "__main__":
    main()
