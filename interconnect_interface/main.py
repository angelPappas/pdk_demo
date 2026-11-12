"""Builds the INTERCONNECT PDK from the database. Run from the repo root:  python -m interconnect_interface.main"""
import sys
from pathlib import Path

try:                                    # python -m interconnect_interface.main
	from . import cml_compiler as cml
	from .photonic_components import PhotonicComponent
except ImportError:                     # python interconnect_interface/main.py
	import cml_compiler as cml
	from photonic_components import PhotonicComponent

FOUNDRY_NAME = "pdk_demo"
DATABASE = Path(__file__).resolve().parent.parent / "database"

# 1. Parse database -> components that are ready to be built.
found = PhotonicComponent.discover(DATABASE)
ready = [c for c in found if c.is_ready()]
if len(sys.argv) > 1:                                   # e.g.  python -m interconnect_interface.main wg_te_cband_ydir
	ready = [c for c in ready if c.name in sys.argv[1:]]
for c in found:
	print(f"{'+' if c in ready else '-'} {c.name}" + (f"  (template {c.template})" if c in ready else "  (not ready, skipped)"))
if not ready:
	raise SystemExit("No component is ready to be built.")
if len({c.template for c in ready}) != len(ready):
	raise SystemExit("Two ready components share one template; deploy them separately (not supported yet).")

# 2. Template library named pdk_demo.
cml.deploy_template(FOUNDRY_NAME)

# 3. Per component: create it from its template, then replace the template data with the database data.
foundry_dir = cml.foundry_dir(FOUNDRY_NAME)
for c in ready:
	cml.add_element(FOUNDRY_NAME, c.template, c.name)
	c.update(foundry_dir)

# 4. All other components: only the ready ones are built, and the template's user-created elements are removed.
print("Removed user-created template elements:", cml.remove_user_created(FOUNDRY_NAME))

# 5. Build the library.
cml_file = cml.build_library(FOUNDRY_NAME, elements=[c.name for c in ready])
print(cml_file)
cml.copy_to_repo(FOUNDRY_NAME)