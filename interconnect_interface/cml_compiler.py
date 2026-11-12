import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

CML_BAT = r"C:\Program Files\Lumerical\v261\CML_Compiler\bin\cml-compiler.bat"

FOUNDRY_NAME = "lumfoundry_template"
WORK_DIR = Path("/mnt/c/pdk_work")        # Windows side: compiler cwd + scratch
REPO_ROOT = Path.cwd()                    # run this from the repo root


def foundry_dir(name: str = FOUNDRY_NAME) -> Path:
    """Windows-side library source directory."""
    return WORK_DIR / name


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


def deploy_template(name: str = FOUNDRY_NAME, fresh: bool = True) -> None:
    """Deploy the full lumfoundry template into WORK_DIR and, if `name` differs, rename the folder to it."""
    target = foundry_dir(name)
    default = foundry_dir(FOUNDRY_NAME)
    if fresh:
        for d in {target, default}:
            if d.exists():
                shutil.rmtree(d)
    cml("template")                                   # always creates WORK_DIR/lumfoundry_template
    if not default.exists():
        raise RuntimeError(f"Expected {default} after deploy, but it doesn't exist")
    if target != default:
        _move(default, target)


def _move(src: Path, dst: Path, tries: int = 10) -> None:
    """Rename a folder on /mnt/c. Windows often still holds a handle on freshly extracted files
    (compiler, indexer, antivirus), which makes a plain rename fail with PermissionError, so retry."""
    for _ in range(tries):
        try:
            src.rename(dst)
            return
        except PermissionError:
            time.sleep(1)
    shutil.copytree(src, dst)                           # fallback: copy, then try to remove the original
    shutil.rmtree(src, ignore_errors=True)


def add_element(name: str, template: str, new_name: str) -> None:
    """Create element `new_name` from `template` inside the deployed library (compiler runs inside it)."""
    cml("template", "--element_list", template, "--rename", new_name, cwd=foundry_dir(name),
        answers={MASTER_PROMPT: "1"})                  # asks which library data file; 1 = lumfoundry_template.json
    if not (foundry_dir(name) / "source" / new_name).is_dir():
        raise RuntimeError(f"Element folder source/{new_name} was not created")


def remove_user_created(name: str = FOUNDRY_NAME) -> list[str]:
    """Empty source/user_created (the template ships e.g. custom_MZM there). The compiler builds everything in
    that folder whatever --element_list says, and those template elements can fail ('Failed to evaluate code')."""
    folder = foundry_dir(name) / "source" / "user_created"
    removed = []
    if folder.is_dir():
        for item in folder.iterdir():
            shutil.rmtree(item) if item.is_dir() else item.unlink()
            removed.append(item.name)
    return removed


DEFAULT_TEST_ELEMENTS = ["wg_strip_straight_c", "wg_bend_90"]
MASTER_PROMPT = r"Please enter one of the above\(\d+-\d+\):"


def build_library(
    name: str = FOUNDRY_NAME,
    elements: list[str] | None = None,
    master_choice: str = "1",
    validate_first: bool = True,
    extra_args: list[str] | None = None,
) -> Path:
    """Build the INTERCONNECT CML from the deployed library source folder.

    elements:      element names to build (empty/None -> DEFAULT_TEST_ELEMENTS).
    master_choice: number typed if the compiler asks which master file to use.
    """
    wdir = foundry_dir(name)
    if not wdir.exists():
        raise RuntimeError(f"{wdir} not found, deploy the template first")

    elements = elements or DEFAULT_TEST_ELEMENTS
    el = ["--element_list", *elements]
    extra = list(extra_args or [])
    answers = {MASTER_PROMPT: master_choice}
    out_dir = wdir / "artifacts" / "interconnect"

    for old in out_dir.glob("*.cml"):         # make sure the result is from this run
        old.unlink()

    if validate_first:
        cml("validate", *el, *extra, cwd=wdir, answers=answers)
    cml("library", *el, *extra, cwd=wdir, answers=answers)

    cml_files = sorted(out_dir.glob("*.cml"))
    if not cml_files:
        raise RuntimeError("Build finished but no .cml found in artifacts/interconnect")
    return cml_files[0]


def copy_to_repo(name: str = FOUNDRY_NAME) -> None:
    """Copy the Windows-side folder into the repo under the same name."""
    dst = REPO_ROOT / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(foundry_dir(name), dst)
    print(f"Copied {foundry_dir(name)} -> {dst}")


if __name__ == "__main__":
    # cml("--help")
    deploy_template()
    cml_path = build_library()
    print(cml_path)
    copy_to_repo()