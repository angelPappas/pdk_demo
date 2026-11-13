"""Finds out which part of our setup makes the library build fail ('Failed to evaluate code').
Each experiment deploys a fresh library in /mnt/c/pdk_work/<folder> and builds one element.
Run from the repo root:  python -m interconnect_interface.experiments      (takes a few minutes)
"""
import contextlib
import io
import shutil
from pathlib import Path

try:
	from . import cml_compiler as cml
except ImportError:
	import cml_compiler as cml

_orig_cml = cml.cml                                     # every compiler call gets a 3 minute limit here
cml.cml = lambda *a, **k: _orig_cml(*a, **{"timeout": 180, **k})

REPO = Path(__file__).resolve().parent.parent
OUR_WG = REPO / "database/passives/waveguides/wg_te_cband_ydir/wg_te_cband_ydir.json"


def stock(folder, element):
	cml.deploy_template(folder)
	return folder, element


def renamed(folder, element, new, clean=False):
	cml.deploy_template(folder)
	cml.add_element(folder, element, new)
	if clean:
		cml.remove_user_created(folder)
	return folder, new


def our_data_in_template_name(folder):
	e = "wg_strip_straight_parameterized"
	cml.deploy_template(folder)
	shutil.copy2(OUR_WG, cml.foundry_dir(folder) / "source" / e / f"{e}.json")
	return folder, e


EXPERIMENTS = [
	("A  stock waveguide_simple, default folder name", lambda: stock("lumfoundry_template", "wg_strip_straight_c")),
	("B  same, folder renamed pdk_demo", lambda: stock("pdk_demo", "wg_strip_straight_c")),
	("C  stock parameterized waveguide (control)", lambda: stock("lumfoundry_template", "wg_strip_straight_parameterized")),
	("D  stock element, renamed with --rename", lambda: renamed("lumfoundry_template", "wg_strip_straight_c", "wg_test")),
	("E  as D, user_created emptied", lambda: renamed("lumfoundry_template", "wg_strip_straight_c", "wg_test", clean=True)),
	("F  OUR waveguide json in the template's own name", lambda: our_data_in_template_name("lumfoundry_template")),
]

results = []
for title, setup in EXPERIMENTS:
	buf = io.StringIO()
	try:
		with contextlib.redirect_stdout(buf):
			folder, element = setup()
			cml.build_library(folder, elements=[element])
		results.append((title, "PASS"))
	except Exception as e:
		results.append((title, "FAIL: " + str(e).strip().splitlines()[-1][:100]))
	print(f"{results[-1][1][:4]}  {title}", flush=True)

print("\n==== summary ====")
for t, r in results:
	print(f"{r:<60} {t}")