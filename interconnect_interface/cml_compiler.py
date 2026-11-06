import re
import shutil
import subprocess
import threading
from pathlib import Path

CML_BAT = r"C:\Program Files\Lumerical\v261\CML_Compiler\bin\cml-compiler.bat"

FOUNDRY_NAME = "lumfoundry_template"
WORK_DIR = Path("/mnt/c/pdk_work")        # Windows side: compiler cwd + scratch
REPO_ROOT = Path.cwd()                    # run this from the repo root

WIN_FOUNDRY_DIR = WORK_DIR / FOUNDRY_NAME
REPO_FOUNDRY_DIR = REPO_ROOT / FOUNDRY_NAME


def cml(
    *args,
    cwd: Path = WORK_DIR,
    check: bool = True,
    timeout: int | None = 600,
    answers: dict[str, str] | None = None,
) -> int:
    """Run cml-compiler, streaming its output live.

    answers: {regex: reply}. When the output matches a regex (e.g. a prompt),
             the reply is typed into the compiler. Each entry is used once.
             Prompts that aren't listed get end-of-input, so they fail instead of hanging.
    """
    cwd.mkdir(parents=True, exist_ok=True)
    cmd = ["cmd.exe", "/c", CML_BAT, *map(str, args)]
    print(cmd)

    pending = {re.compile(p): a for p, a in (answers or {}).items()}
    proc = subprocess.Popen(
        cmd, cwd=cwd,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    if not pending:
        proc.stdin.close()

    timed_out = threading.Event()

    def _kill():
        timed_out.set()
        proc.kill()

    timer = threading.Timer(timeout, _kill) if timeout else None
    if timer:
        timer.start()

    out, buf = [], ""
    try:
        while True:
            chunk = proc.stdout.read1(1024)          # returns as soon as data arrives
            if not chunk:
                break
            text = chunk.decode(errors="replace")
            print(text, end="", flush=True)
            out.append(text)
            buf += text
            for rx, reply in list(pending.items()):
                if rx.search(buf):
                    proc.stdin.write((reply + "\n").encode())
                    proc.stdin.flush()
                    print(f"[answered: {reply}]")
                    del pending[rx]
                    buf = ""
                    break
        proc.wait()
    finally:
        if timer:
            timer.cancel()
        try:
            proc.stdin.close()
        except OSError:
            pass

    if timed_out.is_set():
        raise RuntimeError(f"cml-compiler timed out after {timeout}s\n{''.join(out)}")
    if check and proc.returncode != 0:
        raise RuntimeError(f"cml-compiler failed (exit {proc.returncode})\n{''.join(out)}")
    return proc.returncode


def deploy_template(fresh: bool = True) -> None:
    """Deploy lumfoundry_template into WORK_DIR (the compiler's cwd)."""
    if fresh and WIN_FOUNDRY_DIR.exists():
        shutil.rmtree(WIN_FOUNDRY_DIR)
    cml("template")
    if not WIN_FOUNDRY_DIR.exists():
        raise RuntimeError(f"Expected {WIN_FOUNDRY_DIR} after deploy, but it doesn't exist")


DEFAULT_TEST_ELEMENTS = ["wg_strip_straight_c", "wg_bend_90"]
MASTER_PROMPT = r"Please enter one of the above\(\d+-\d+\):"


def build_library(
    elements: list[str] | None = None,
    master_choice: str = "1",
    validate_first: bool = True,
    extra_args: list[str] | None = None,
) -> Path:
    """Build the INTERCONNECT CML from the deployed library source folder.

    elements:      element names to build (empty/None -> DEFAULT_TEST_ELEMENTS).
    master_choice: number typed if the compiler asks which master file to use.
    """
    if not WIN_FOUNDRY_DIR.exists():
        raise RuntimeError(f"{WIN_FOUNDRY_DIR} not found, deploy the template first")

    elements = elements or DEFAULT_TEST_ELEMENTS
    el = ["--element_list", *elements]
    extra = list(extra_args or [])
    answers = {MASTER_PROMPT: master_choice}
    out_dir = WIN_FOUNDRY_DIR / "artifacts" / "interconnect"

    for old in out_dir.glob("*.cml"):         # make sure the result is from this run
        old.unlink()

    if validate_first:
        cml("validate", *el, *extra, cwd=WIN_FOUNDRY_DIR, answers=answers)
    cml("library", *el, *extra, cwd=WIN_FOUNDRY_DIR, answers=answers)

    cml_files = sorted(out_dir.glob("*.cml"))
    if not cml_files:
        raise RuntimeError("Build finished but no .cml found in artifacts/interconnect")
    return cml_files[0]


def copy_to_repo() -> None:
    """Copy the Windows-side folder into the repo under the same name."""
    if REPO_FOUNDRY_DIR.exists():
        shutil.rmtree(REPO_FOUNDRY_DIR)
    shutil.copytree(WIN_FOUNDRY_DIR, REPO_FOUNDRY_DIR)
    print(f"Copied {WIN_FOUNDRY_DIR} -> {REPO_FOUNDRY_DIR}")


if __name__ == "__main__":
    # cml("--help")
    deploy_template()
    cml_path = build_library()
    print(cml_path)
    copy_to_repo()