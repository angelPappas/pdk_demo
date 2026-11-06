import shutil
import subprocess
from pathlib import Path

CML_BAT = r"C:\Program Files\Lumerical\v261\CML_Compiler\bin\cml-compiler.bat"

FOUNDRY_NAME = "lumfoundry_template"
WORK_DIR = Path("/mnt/c/pdk_work")        # Windows side: compiler cwd + scratch
REPO_ROOT = Path.cwd()                    # run this from the repo root

WIN_FOUNDRY_DIR = WORK_DIR / FOUNDRY_NAME
REPO_FOUNDRY_DIR = REPO_ROOT / FOUNDRY_NAME


def cml(*args, cwd: Path = WORK_DIR, check: bool = True) -> subprocess.CompletedProcess:
    """Run cml-compiler with the given arguments."""
    cwd.mkdir(parents=True, exist_ok=True)
    cmd = ["cmd.exe", "/c", CML_BAT, *map(str, args)]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"cml-compiler failed (exit {result.returncode})\n"
            f"cmd: {' '.join(cmd)}\n{result.stdout}\n{result.stderr}"
        )
    return result


def deploy_template(fresh: bool = True) -> None:
    """Deploy lumfoundry_template into WORK_DIR (the compiler's cwd)."""
    if fresh and WIN_FOUNDRY_DIR.exists():
        shutil.rmtree(WIN_FOUNDRY_DIR)
    cml("template")
    if not WIN_FOUNDRY_DIR.exists():
        raise RuntimeError(f"Expected {WIN_FOUNDRY_DIR} after deploy, but it doesn't exist")


def copy_to_repo() -> None:
    """Copy the Windows-side folder into the repo under the same name."""
    if REPO_FOUNDRY_DIR.exists():
        shutil.rmtree(REPO_FOUNDRY_DIR)
    shutil.copytree(WIN_FOUNDRY_DIR, REPO_FOUNDRY_DIR)
    print(f"Copied {WIN_FOUNDRY_DIR} -> {REPO_FOUNDRY_DIR}")


if __name__ == "__main__":
    deploy_template()
    copy_to_repo()