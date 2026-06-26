# Installation

```bash
pip install logging-tee
```

# Usage

```python
import logging
from tqdm import tqdm
import time

from logging_tee import setup_logger

if __name__ == "__main__":
    setup_logger(log_file="output.log", level=logging.DEBUG)
    logger = logging.getLogger(__name__)

    for i in tqdm(
        range(2),
        desc="Processing",
    ):
        time.sleep(0.03)
        logger.info("Processing item %d", i)

    for outer_idx in tqdm(
        range(2),
        desc="Outer",
    ):
        for inner_idx in tqdm(
            range(3),
            desc=f"Inner {outer_idx}",
        ):
            time.sleep(0.02)
            if inner_idx % 5 == 0:
                print(f"Nested step outer={outer_idx} inner={inner_idx}")
        logger.info(f"Completed outer={outer_idx}")

    print("from print statement")
    print("multiple lines\nfrom print statement 2")
    logger.debug("Single line")
    logger.debug("Multiple lines:\nnext line")
    logger.debug("Another single line")
    logger.debug("Multiple lines:\n%s", "next line\nnext line 2")
    logger.warning("Warning message\nwith multiple lines\nand should be logged properly.")
    logger.error("Error message\nwith multiple lines\nand should be logged properly.")
    raise ValueError("This is an error message\nwith multiple lines\nand should be logged properly.")
```

# Contributing

Build the package

```bash
python -m pip install build
python -m build
python install dist/*.whl
python -c "import logging_tee; print(logging_tee)"
```

Upload to TestPyPI first

```bash
python -m pip install twine
python -m twine upload --repository testpypi dist/*
```

Upload to PyPi

```bash
python -m twine upload dist/*
```