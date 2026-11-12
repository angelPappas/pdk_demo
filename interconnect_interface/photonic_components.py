"""Database components and how each one is added to the INTERCONNECT library source directory."""
import json
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

PREFIXES = ("wg", "dc", "gc")


class PhotonicComponent(ABC):
	"""A component folder in the database: database/.../<name>/<name>.json (+ <name>.dat for S-matrix parts)."""

	def __init__(self, folder: Path) -> None:
		self.folder = folder
		self.name = folder.name
		self.json_file = folder / f"{self.name}.json"

	@classmethod
	def create(cls, folder: Path) -> "PhotonicComponent":
		kind = {"wg": waveguide, "dc": directional_coupler, "gc": grating_coupler}[folder.name.casefold()[:2]]
		return kind(folder)

	@classmethod
	def discover(cls, database_path: str | Path) -> list["PhotonicComponent"]:
		"""All component folders (wg*, dc*, gc*) anywhere inside the database."""
		root = Path(database_path)
		if not root.is_dir():
			raise NotADirectoryError(f"Database folder does not exist: {root}")
		return [cls.create(f) for f in sorted(root.rglob("*"))
				if f.is_dir() and f.name.casefold().startswith(PREFIXES)]

	@property
	@abstractmethod
	def template(self) -> str | None:
		"""Name of the lumfoundry template element this component is built from."""

	def is_ready(self) -> bool:
		"""True when the component has everything needed to go into INTERCONNECT."""
		return self.json_file.is_file() and self.template is not None

	def update(self, foundry_dir: Path) -> None:
		"""Put the database data into the deployed (and renamed) template element."""
		dest = foundry_dir / "source" / self.name
		if not dest.is_dir():
			raise RuntimeError(f"Element folder {dest} not found; was the template deployed with --rename?")
		shutil.copy2(self.json_file, dest / f"{self.name}.json")


class waveguide(PhotonicComponent):
	# the library master file ties an element to a photonic model, so the template must match the json
	TEMPLATES = {"waveguide_simple": "wg_strip_straight_c",
				 "wg_parameterized": "wg_strip_straight_parameterized"}

	@property
	def template(self) -> str | None:
		if not self.json_file.is_file():
			return None
		model = json.loads(self.json_file.read_text()).get("model_data", {}).get("photonic_model")
		return self.TEMPLATES.get(model)


class directional_coupler(PhotonicComponent):
	"""S-parameter component (spar_fixed): the json plus <name>_S_params.txt, both copied into the element."""
	TEMPLATES = {"spar_fixed": "dc_strip_te_c"}

	@property
	def sparams_file(self) -> Path:
		return self.folder / f"{self.name}_S_params.txt"

	@property
	def template(self) -> str | None:
		if not self.json_file.is_file():
			return None
		model = json.loads(self.json_file.read_text()).get("model_data", {}).get("photonic_model")
		return self.TEMPLATES.get(model)

	def is_ready(self) -> bool:
		return super().is_ready() and self.sparams_file.is_file()

	def update(self, foundry_dir: Path) -> None:
		super().update(foundry_dir)
		shutil.copy2(self.sparams_file, foundry_dir / "source" / self.name / self.sparams_file.name)


class grating_coupler(PhotonicComponent):
	template = None                       # not ready yet


def main() -> None:
	import argparse
	parser = argparse.ArgumentParser(description="List database components and whether they are ready.")
	parser.add_argument("database_path")
	for c in PhotonicComponent.discover(parser.parse_args().database_path):
		print(f"{c.name}: {'ready, template ' + c.template if c.is_ready() else 'not ready'}")


if __name__ == "__main__":
	main()