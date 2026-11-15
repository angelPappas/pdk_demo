"""Builds the INTERCONNECT PDK from the database. Run from the repo root:  python -m interconnect_interface.main"""
import sys
from pathlib import Path

try:                                    # python -m interconnect_interface.main
	from . import cml_compiler as cml
	from .photonic_components import PhotonicComponent
except ImportError:                     # python interconnect_interface/main.py
	import cml_compiler as cml
	from photonic_components import PhotonicComponent

FOUNDRY_NAME = "pdk_demo"                      # folder name on disk
LIBRARY_NAME = FOUNDRY_NAME                     # library name inside INTERCONNECT (master file "foundry_name")
PROCESS_PREFIX = "tfln_"                          # prefix added to every element name; None keeps the template's "lum_", "" removes it
args = sys.argv[1:]
if "--foundry" in args:                                  # experiment: e.g. --foundry lumfoundry_template (no folder rename)
	i = args.index("--foundry")
	FOUNDRY_NAME = args[i + 1]
	args = args[:i] + args[i + 2:]
DATABASE = Path(__file__).resolve().parent.parent / "database"

# 1. Parse database -> components that are ready to be built.
found = PhotonicComponent.discover(DATABASE)
ready = [c for c in found if c.is_ready()]
if args:                                   # e.g.  python -m interconnect_interface.main wg_te_cband_ydir
	ready = [c for c in ready if c.name in args]
for c in found:
	print(f"{'+' if c in ready else '-'} {c.name}" + ((f"  (template {c.template})" if c.template else "  (compound element, user_created)") if c in ready else "  (not ready, skipped)"))
if not ready:
	raise SystemExit("No component is ready to be built.")
regular = [c for c in ready if c.template]                # built from a lumfoundry template
compounds = [c for c in ready if not c.template]          # .ice + .svg, copied into source/user_created
shared = sorted({c.template for c in regular if sum(d.template == c.template for d in regular) > 1})
if shared:                              # each element is created from the compiler's template store under its own name
	print(f"Note: several components share the template(s) {', '.join(shared)}; each is added under its own name.")

# 2. Template library named pdk_demo.
cml.deploy_template(FOUNDRY_NAME)

# 3. Per component: create it from its template, then replace the template data with the database data.
foundry_dir = cml.foundry_dir(FOUNDRY_NAME)
for c in regular:
	cml.add_element(FOUNDRY_NAME, c.template, c.name)
	c.update(foundry_dir)

# 4. All other components: only the ready ones are built, and the template's user-created elements are removed.
print("Removed user-created template elements:", cml.remove_user_created(FOUNDRY_NAME))
for c in compounds:                                       # after the clean-up, which empties source/user_created
	c.update(foundry_dir)
	print(f"Added compound element {c.name} to source/user_created")

cml.set_library_name(FOUNDRY_NAME, LIBRARY_NAME, PROCESS_PREFIX)

# 5. Build the library.
cml_file = cml.build_library(FOUNDRY_NAME, elements=[c.name for c in regular])   # compounds are built from user_created whatever this list says
print(cml_file)
cml.copy_to_repo(FOUNDRY_NAME)