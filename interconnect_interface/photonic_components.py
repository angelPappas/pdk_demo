from abc import ABC, abstractmethod
import argparse
from pathlib import Path


class PhotonicComponent(ABC):
	"""Base class for photonic components."""
	@classmethod
	def create(cls, database_path: str, name: str, interconnect_path: str) -> "PhotonicComponent":
		"""Create the component type indicated by the database folder name."""
		folder_name = name.casefold()
		if folder_name.startswith("dc"):
			component_type = directional_coupler
		elif folder_name.startswith("gc"):
			component_type = grating_coupler
		else:
			raise ValueError(f"Unsupported photonic component folder name: {name}")
		return component_type(database_path, name, interconnect_path)

	@classmethod
	def discover(cls, database_path: str, interconnect_path: str) -> list["PhotonicComponent"]:
		"""Find supported component folders anywhere inside a database folder."""
		root = Path(database_path)
		if not root.is_dir():
			raise NotADirectoryError(f"Database folder does not exist: {database_path}")

		components = []
		for folder in sorted(root.rglob("*")):
			if not folder.is_dir() or not folder.name.casefold().startswith(("dc", "gc")):
				continue
			components.append(cls.create(str(folder.parent), folder.name, interconnect_path))
		return components

	def __init__(self, database_path: str, name: str, interconnect_path: str) -> None:
		self.database_path = database_path
		self.name = name
		self.interconnect_path = interconnect_path

	@abstractmethod
	def update(self) -> None:
		"""Necessary steps for correct implementation of component in Interconnect."""


class directional_coupler(PhotonicComponent):
	def update(self) -> None:
		pass


class grating_coupler(PhotonicComponent):
	def update(self) -> None:
		pass


def main() -> None:
	parser = argparse.ArgumentParser(description="Discover photonic components in a database.")
	parser.add_argument("database_path", help="Path to the component database folder")
	parser.add_argument("interconnect_path", help="Path to the Interconnect installation")
	args = parser.parse_args()

	components = PhotonicComponent.discover(args.database_path, args.interconnect_path)
	for component in components:
		print(component.name)


if __name__ == "__main__":
	main()
