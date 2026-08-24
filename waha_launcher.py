import os
import subprocess
import shutil
import logging
import time
import httpx
from typing import Tuple

logger = logging.getLogger(__name__)


class WAHALauncher:
    _is_launching = False

    @staticmethod
    def is_node_available() -> bool:
        return shutil.which("node") is not None or shutil.which("npx") is not None

    @classmethod
    def is_waha_server_running(cls, port: int = 3000) -> bool:
        """Synchronously check if local engine is listening and healthy on port."""
        try:
            resp = httpx.get(f"http://localhost:{port}/health", timeout=1.5)
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def start_waha_engine(cls, port: int = 3000) -> Tuple[bool, str]:
        """
        Launches the embedded Baileys WhatsApp engine (wa_engine/server.js) natively using Node.js.
        Guards against duplicate process spawns on the same port (EADDRINUSE).
        """
        # 1. Check if engine is already running on this port
        if cls.is_waha_server_running(port=port):
            return True, f"CyberSolu Baileys WhatsApp Gateway already active on http://localhost:{port}!"

        if cls._is_launching:
            return True, "Gateway engine launch already in progress..."

        cls._is_launching = True
        try:
            if not cls.is_node_available():
                return False, "Node.js was not found on your system. Please ensure Node.js is installed."

            wa_engine_dir = os.path.join(os.path.dirname(__file__), "wa_web_engine")
            server_js = os.path.join(wa_engine_dir, "server.js")

            if not os.path.exists(server_js):
                return False, f"Embedded engine server not found at {server_js}"

            # Install dependencies if node_modules missing
            node_modules = os.path.join(wa_engine_dir, "node_modules")
            if not os.path.exists(node_modules):
                try:
                    npm_bin = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
                    res = subprocess.run([npm_bin, "install"], cwd=wa_engine_dir, capture_output=True, text=True, timeout=90, shell=(os.name == 'nt'))
                    if res.returncode != 0:
                        return False, f"Failed to install engine dependencies: {res.stderr.strip()}"
                except Exception as e:
                    return False, f"Failed to run npm install in wa_engine: {e}"

            # Launch node server.js in background
            env = os.environ.copy()
            env["PORT"] = str(port)
            node_bin = shutil.which("node.exe") or shutil.which("node") or "node"

            # Launch process with Windows detachment flags so it runs as an independent daemon
            creation_flags = 0
            if os.name == 'nt':
                creation_flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP

            subprocess.Popen(
                [node_bin, "server.js"],
                cwd=wa_engine_dir,
                env=env,
                shell=False,
                creationflags=creation_flags
            )

            # Poll for health check up to 5 seconds
            for _ in range(10):
                time.sleep(0.5)
                if cls.is_waha_server_running(port=port):
                    return True, f"CyberSolu WhatsApp Web Gateway active on http://localhost:{port}!"

            return True, f"CyberSolu WhatsApp Web Gateway launched on http://localhost:{port} (initializing)..."
        except Exception as e:
            return False, f"Failed to launch node server.js: {e}"
        finally:
            cls._is_launching = False

    @classmethod
    def stop_waha_engine(cls, port: int = 3000) -> bool:
        """Stops any running node processes and destroys all browser instances listening on the engine port."""
        # 1. Non-blocking graceful API shutdown
        try:
            httpx.post(f"http://localhost:{port}/api/shutdown", timeout=0.25)
        except Exception:
            pass

        # 2. Kill node/chromium process tree on Windows immediately
        if os.name == 'nt':
            try:
                res = subprocess.run(f"netstat -ano | findstr :{port}", capture_output=True, text=True, shell=True)
                for line in res.stdout.strip().splitlines():
                    parts = line.split()
                    if len(parts) >= 5 and "LISTENING" in parts:
                        pid = parts[-1]
                        subprocess.run(f"taskkill /F /T /PID {pid}", shell=True, capture_output=True)
            except Exception:
                pass
        return True

    @classmethod
    def restart_waha_engine(cls, port: int = 3000) -> Tuple[bool, str]:
        """Restarts the Baileys gateway engine cleanly."""
        cls.stop_waha_engine(port=port)
        time.sleep(1.0)
        return cls.start_waha_engine(port=port)
