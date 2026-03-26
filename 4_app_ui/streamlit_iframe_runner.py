# streamlit_iframe_runner.py
# Streamlit shell: start uI (Vite) dev server and embed it in an iframe.
# Run: cd data_collection/4_app && streamlit run streamlit_iframe_runner.py

import logging
import shutil
import socket
import subprocess
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

APP_DIR = Path(__file__).resolve().parent
UI_DIR = APP_DIR / "uI"
VITE_HOST = "127.0.0.1"
VITE_PORT = 5173
IFRAME_HEIGHT_PX = 1100
PORT_WAIT_SEC = 45
POLL_INTERVAL_SEC = 0.4

# single message for missing npm (avoid copy-paste)
_MSG_NO_NPM = "npm not on PATH. Install Node.js and open a new terminal."

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)


def port_open(host, port):
    # localhost: 0.35s is enough; longer timeouts slow down every Streamlit rerun
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def ensure_vite():
    # returns (ok, url, hint); non-empty hint is shown with st.info below

    if not UI_DIR.is_dir():
        return False, "", f"missing `uI` folder\n`{UI_DIR}`"

    url = f"http://{VITE_HOST}:{VITE_PORT}/"

    if not (UI_DIR / "package.json").is_file():
        return False, "", f"missing `package.json`\n`{UI_DIR}`"

    npm = shutil.which("npm")

    # install deps only if node_modules is absent
    if not (UI_DIR / "node_modules").is_dir():
        with st.spinner("Installing packages (first run only)..."):
            if not npm:
                return False, "", _MSG_NO_NPM
            completed = subprocess.run(
                [npm, "install", "--legacy-peer-deps"],
                cwd=UI_DIR,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if completed.returncode != 0:
                tail = (completed.stderr or completed.stdout or "")[-2000:]
                logging.error("npm install: %s", tail)
                return (
                    False,
                    "",
                    "npm install failed > run `npm install --legacy-peer-deps` inside `uI`",
                )

    if port_open(VITE_HOST, VITE_PORT):
        return True, url, f"port {VITE_PORT} already in use (e.g. dev server from another terminal)"

    key = "vite_child"
    if key not in st.session_state:
        st.session_state[key] = None

    child = st.session_state[key]
    if child is not None and child.poll() is not None:
        logging.warning("vite child died code=%s", child.returncode)
        st.session_state[key] = None
        child = None

    if child is None:
        if not npm:
            return False, "", _MSG_NO_NPM
        try:
            # new process group - fewer signal clashes with parent (OS-dependent; helps on mac when testing)
            st.session_state[key] = subprocess.Popen(
                [npm, "run", "dev", "--", "--host", VITE_HOST, "--port", str(VITE_PORT)],
                cwd=UI_DIR,
                stdout=None,
                stderr=None,
                start_new_session=True,
            )
        except OSError as e:
            logging.exception("vite start")
            return False, "", f"failed to start Vite: {e}"

    saw_port = False
    with st.spinner("Waiting for Vite..."):
        deadline = time.monotonic() + float(PORT_WAIT_SEC)
        while time.monotonic() < deadline:
            if port_open(VITE_HOST, VITE_PORT):
                saw_port = True
                break
            time.sleep(POLL_INTERVAL_SEC)

    if not saw_port:
        return (
            False,
            "",
            f"no reply on port {VITE_PORT}.\n"
            f"`cd {UI_DIR}`\n"
            f"`npm run dev -- --host 127.0.0.1 --port {VITE_PORT}`\n"
            f"then refresh this page",
        )

    return True, url, ""


# page config
st.set_page_config(
    page_title="Restaurant Review Flash Berlin",
    layout="wide",
)

st.title("Restaurant Review Flash Berlin")
st.caption(f"UI path: `{UI_DIR}`")

ok, url, hint = ensure_vite()
if hint:
    st.info(hint)

with st.expander("Manual run"):
    st.markdown(
        f"""
- `cd {UI_DIR}`
- `npm install --legacy-peer-deps` (first time only)
- `npm run dev -- --host 127.0.0.1 --port {VITE_PORT}`
- open in browser: `{url}`
"""
    )

if not ok:
    st.error("iframe failed > start Vite using the commands under **Manual run**, then refresh.")
else:
    components.iframe(url, height=IFRAME_HEIGHT_PX, scrolling=True)
