"""Builds the interconnect PDK."""

from cml_compiler import deploy_template

FOUNDRY_NAME = "Demo_TFLN_PDK"

# 1. Parse database -> extract list of components to-be-built.

# 2. Build template lumfoundry
deploy_template(fresh=True)
# 3. For each component:
# i. Create a component from its template
# ii. Make any necessary updates to the component

# 4. Delete all other components

# 5. Build library