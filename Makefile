format: isort black
	-flake8
	-mypy .

lint:
	-isort --check-only
	-black --check .
	-flake8 .
	-mypy .

black:
	black .

isort:
	isort .

flake8:
	flake8

mypy:
	mypy .