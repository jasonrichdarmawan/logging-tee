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
    logger = logging.getLogger()
    logger2 = logging.getLogger("test_logger2")

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
    logger2.info("Logger2 info message\nwith multiple lines\nand should be logged properly.")
    raise ValueError("This is an error message\nwith multiple lines\nand should be logged properly.")
```

output.log
```
2026-06-27 13:57:02,390 root INFO      Processing item 0
2026-06-27 13:57:02,421 root INFO      Processing item 1
2026-06-27 13:57:02,421 root INFO      tqdm[Processing] done: 2/2 (100.0%), elapsed 0.1s, 32.95 it/s, ETA 0.0s
2026-06-27 13:57:02,442 root INFO      Nested step outer=0 inner=0
2026-06-27 13:57:02,482 root INFO      tqdm[Inner 0] done: 3/3 (100.0%), elapsed 0.1s, 49.25 it/s, ETA 0.0s
2026-06-27 13:57:02,483 root INFO      Completed outer=0
2026-06-27 13:57:02,504 root INFO      Nested step outer=1 inner=0
2026-06-27 13:57:02,544 root INFO      tqdm[Inner 1] done: 3/3 (100.0%), elapsed 0.1s, 49.56 it/s, ETA 0.0s
2026-06-27 13:57:02,545 root INFO      Completed outer=1
2026-06-27 13:57:02,545 root INFO      tqdm[Outer] progress: 2/2 (100.0%), elapsed 0.1s, 16.19 it/s, ETA 0.0s
2026-06-27 13:57:02,545 root INFO      tqdm[Outer] done: 2/2 (100.0%), elapsed 0.1s, 16.19 it/s, ETA 0.0s
2026-06-27 13:57:02,546 root INFO      from print statement
2026-06-27 13:57:02,546 root INFO      multiple lines
2026-06-27 13:57:02,546 root INFO      from print statement 2
2026-06-27 13:57:02,546 root DEBUG     Single line
2026-06-27 13:57:02,546 root DEBUG     Multiple lines:
2026-06-27 13:57:02,546 root DEBUG     next line
2026-06-27 13:57:02,546 root DEBUG     Another single line
2026-06-27 13:57:02,546 root DEBUG     Multiple lines:
2026-06-27 13:57:02,546 root DEBUG     next line
2026-06-27 13:57:02,546 root DEBUG     next line 2
2026-06-27 13:57:02,546 root WARNING   Warning message
2026-06-27 13:57:02,546 root WARNING   with multiple lines
2026-06-27 13:57:02,546 root WARNING   and should be logged properly.
2026-06-27 13:57:02,546 root ERROR     Error message
2026-06-27 13:57:02,546 root ERROR     with multiple lines
2026-06-27 13:57:02,546 root ERROR     and should be logged properly.
2026-06-27 13:57:02,547 test_logger2 INFO      Logger2 info message
2026-06-27 13:57:02,547 test_logger2 INFO      with multiple lines
2026-06-27 13:57:02,547 test_logger2 INFO      and should be logged properly.
2026-06-27 13:57:02,547 root ERROR     Uncaught exception
2026-06-27 13:57:02,547 root ERROR     Traceback (most recent call last):
2026-06-27 13:57:02,547 root ERROR       File "/home/npu-tao/micromamba/envs/hipporag/lib/python3.10/runpy.py", line 196, in _run_module_as_main
2026-06-27 13:57:02,547 root ERROR         return _run_code(code, main_globals, None,
2026-06-27 13:57:02,547 root ERROR       File "/home/npu-tao/micromamba/envs/hipporag/lib/python3.10/runpy.py", line 86, in _run_code
2026-06-27 13:57:02,547 root ERROR         exec(code, run_globals)
2026-06-27 13:57:02,547 root ERROR       File "/media/npu-tao/disk4T/jason/logging-tee/examples/demo.py", line 41, in <module>
2026-06-27 13:57:02,547 root ERROR         raise ValueError("This is an error message\nwith multiple lines\nand should be logged properly.")
2026-06-27 13:57:02,547 root ERROR     ValueError: This is an error message
2026-06-27 13:57:02,547 root ERROR     with multiple lines
2026-06-27 13:57:02,547 root ERROR     and should be logged properly.
```

# Contributing

Increase `version` in [pyproject.toml](pyproject.toml) file.

Modify the `src` folder.

If using `logging_tee` in other repository

```bash
export PYTHONPATH=<path-to-folder>/src:$PYTHONPATH
python -c "import logging_tee; print(logging_tee)"
```

If using `logging_tee` in this repository

```bash
export PYTHONPATH=src/:$PYTHONPATH
python -c "import logging_tee; print(logging_tee)"
```

Run the test

```
python -m pytest tests -s
```

Build the package

```bash
python -m pip install build
python -m build
pip install dist/*.whl
python -c "import logging_tee; print(logging_tee)"
```

Upload to TestPyPI first

```bash
python -m pip install twine
python -m twine upload --repository testpypi dist/*
python -m pip install --index-url https://test.pypi.org/simple logging-tee
```

Upload to PyPi

```bash
python -m twine upload dist/*
```