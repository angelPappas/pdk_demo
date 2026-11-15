"""Database components and how each one is added to the INTERCONNECT library source directory."""
import json
import re
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

PREFIXES = ("wg", "dc", "gc", "bend", "rr")


class PhotonicComponent(ABC):
	"""A component folder in the database: database/.../<name>/<name>.json (+ <name>.dat for S-matrix parts)."""

	def __init__(self, folder: Path) -> None:
		self.folder = folder
		self.name = folder.name
		self.json_file = folder / f"{self.name}.json"

	@classmethod
	def create(cls, folder: Path) -> "PhotonicComponent":
		name = folder.name.casefold()
		kind = {"wg": waveguide, "dc": directional_coupler, "gc": grating_coupler, "bend": bend_90,
				"rr": compound_ring}[
			"bend" if name.startswith("bend") else name[:2]]
		return kind(folder)

	@classmethod
	def discover(cls, database_path: str | Path) -> list["PhotonicComponent"]:
		"""All component folders anywhere inside the database: a folder <name> that holds <name>.json.
		Grouping folders (wg_bend, wg_straight, ...) have no such json and are not components."""
		root = Path(database_path)
		if not root.is_dir():
			raise NotADirectoryError(f"Database folder does not exist: {root}")
		return [cls.create(f) for f in sorted(root.rglob("*"))
				if f.is_dir() and f.name.casefold().startswith(PREFIXES)
				and ((f / f"{f.name}.json").is_file() or (f / f"{f.name}.ice").is_file())]

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


def rotate_svg_90(path: Path) -> None:
	"""Rotate the picture of an svg file by 90 degrees clockwise (horizontal icon -> vertical icon).
	The content is wrapped in a group with a transform and the canvas (viewBox, width, height) is swapped."""
	text = path.read_text(encoding="utf-8")
	m = re.search(r"<svg\b[^>]*>", text)
	if m is None:
		raise RuntimeError(f"{path} has no <svg> element")
	root = m.group(0)

	def attr(name):
		a = re.search(rf'\s{name}\s*=\s*"([^"]*)"', root)
		return a.group(1) if a else None

	def number(v):
		n = re.match(r"\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", v or "")
		return float(n.group(1)) if n else None

	vb = attr("viewBox")
	if vb:
		minx, miny, w, h = (float(v) for v in re.split(r"[ ,]+", vb.strip()))
	else:
		w, h = number(attr("width")), number(attr("height"))
		if w is None or h is None:
			raise RuntimeError(f"{path}: need a viewBox or numeric width and height to rotate it")
		minx = miny = 0.0
	new_root = root
	new_vb = f"{minx:g} {miny:g} {h:g} {w:g}"
	new_root = re.sub(r'(\sviewBox\s*=\s*)"[^"]*"', rf'\1"{new_vb}"', new_root) if vb else new_root[:-1] + f' viewBox="{new_vb}">'
	wa, ha = attr("width"), attr("height")
	if wa is not None and ha is not None:                     # swap the displayed size, keep the units
		new_root = re.sub(r'(\swidth\s*=\s*)"[^"]*"', lambda _: f'{_.group(1)}"{ha}"', new_root, count=1)
		new_root = re.sub(r'(\sheight\s*=\s*)"[^"]*"', lambda _: f'{_.group(1)}"{wa}"', new_root, count=1)
	group = f'<g transform="translate({minx + miny + h:g} {miny - minx:g}) rotate(90)">'
	end = text.rindex("</svg>")
	body = text[m.end():end]
	path.write_text(text[:m.start()] + new_root + group + body + "</g>" + text[end:], encoding="utf-8")


class waveguide(PhotonicComponent):
	# the library master file ties an element to a photonic model, so the template must match the json
	TEMPLATES = {"waveguide_simple": "wg_strip_straight_c",
				 "wg_parameterized": "wg_strip_straight_parameterized"}

	def update(self, foundry_dir: Path) -> None:
		super().update(foundry_dir)
		if self.name.casefold().endswith("zdir"):           # z-direction waveguide: ports are bottom / top
			dest = foundry_dir / "source" / self.name
			icons = sorted(dest.glob("*.svg"))
			if not icons:
				raise RuntimeError(f"No svg icon found in {dest} to rotate.")
			for icon in icons:
				rotate_svg_90(icon)

	@property
	def template(self) -> str | None:
		if not self.json_file.is_file():
			return None
		model = json.loads(self.json_file.read_text()).get("model_data", {}).get("photonic_model")
		return self.TEMPLATES.get(model)


class _spar_component(PhotonicComponent):
	"""S-parameter component (spar_fixed): the json plus <name>_S_params.txt, both copied into the element."""
	TEMPLATES: dict[str, str] = {}

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


class directional_coupler(_spar_component):
	TEMPLATES = {"spar_fixed": "dc_strip_te_c"}


class grating_coupler(_spar_component):
	"""Grating coupler and its taper as ONE 2-port element (opt_1 waveguide, opt_2 fibre)."""
	TEMPLATES = {"spar_fixed": "gc_strip_te_c"}


class bend_90(_spar_component):
	"""90-degree bend (fixed radius) as a 2-port S-parameter element: opt_1 input, opt_2 output.
	Built on a spar_fixed template that is still free (1x2 MMI), because every template can be used once per library.
	The MMI's icon is replaced by the icon of the wg_bend_90 template."""
	TEMPLATES = {"spar_fixed": "mmi_1x2_strip_te_c"}
	ICON_TEMPLATE = "wg_bend_90"

	def update(self, foundry_dir: Path) -> None:
		super().update(foundry_dir)
		dest = foundry_dir / "source" / self.name
		icon = foundry_dir / "source" / self.ICON_TEMPLATE / f"{self.ICON_TEMPLATE}.svg"
		if not icon.is_file():
			raise RuntimeError(f"Icon {icon} not found (deployed template library).")
		for old in dest.glob("*.svg"):                      # the MMI icon that came with the template
			old.unlink()
		shutil.copy2(icon, dest / f"{self.name}.svg")


class compound_ring(PhotonicComponent):
	"""Several library elements wired into ONE element (a compound), e.g. the single-bus racetrack resonator:
	DC + 4 x bend_90 + straight. It has no photonic model and no template: the database folder holds
	<name>.ice (the compound saved from INTERCONNECT) and <name>.svg (its icon), and both go into
	source/user_created/, which the compiler adds to the library as it is. The elements inside the compound
	must be built in the same library (they are looked up in Design Kits)."""

	@property
	def ice_file(self) -> Path:
		return self.folder / f"{self.name}.ice"

	@property
	def icon_file(self) -> Path:
		return self.folder / f"{self.name}.svg"

	@property
	def template(self) -> str | None:
		return None                                         # not built from a lumfoundry template

	def is_ready(self) -> bool:
		return self.ice_file.is_file() and self.icon_file.is_file()

	def update(self, foundry_dir: Path) -> None:
		dest = foundry_dir / "source" / "user_created"
		dest.mkdir(parents=True, exist_ok=True)
		shutil.copy2(self.ice_file, dest / self.ice_file.name)
		shutil.copy2(self.icon_file, dest / self.icon_file.name)


def main() -> None:
	import argparse
	parser = argparse.ArgumentParser(description="List database components and whether they are ready.")
	parser.add_argument("database_path")
	for c in PhotonicComponent.discover(parser.parse_args().database_path):
		print(f"{c.name}: {'ready, ' + ('template ' + c.template if c.template else 'compound (.ice + .svg)') if c.is_ready() else 'not ready'}")


if __name__ == "__main__":
	main()