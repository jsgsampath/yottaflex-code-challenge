
from pathlib import Path
from tempfile import TemporaryDirectory

from generator_v2 import generate_all
from validator import validate_data


def main():
	with TemporaryDirectory() as temporary_directory:
		root = Path(temporary_directory)
		first_run = root / "first"
		second_run = root / "second"
		generate_all(first_run, scale="starter")
		generate_all(second_run, scale="starter")

		first_files = sorted(
			path.name for path in first_run.iterdir() if path.is_file()
		)
		second_files = sorted(
			path.name for path in second_run.iterdir() if path.is_file()
		)
		if first_files != second_files:
			raise AssertionError("Repeated generation produced different file sets")
		for filename in first_files:
			if (first_run / filename).read_bytes() != (second_run / filename).read_bytes():
				raise AssertionError(f"Repeated generation changed {filename}")

		issues = validate_data(first_run)
		if issues:
			raise AssertionError("Generated data failed validation:\n" + "\n".join(issues))

	print("Reproducibility and generated-data validation passed.")


if __name__ == "__main__":
	main()
