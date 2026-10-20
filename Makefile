.PHONY: test run package

test:
	python -m unittest discover -s tests -v

run:
	python -m pyxils_open

package:
	powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1
